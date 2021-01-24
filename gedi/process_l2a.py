import argparse
import h5py
import os
import numpy as np
import pandas as pd
import geopandas as gp

from typing import List
from shapely.geometry import Point


def gedi_L2A_to_df(
    file_dir: str,
    file_paths: List[str],
    bbox: List[float],
    layers: List[str] = [
        "shot_number",
        "lat_lowestmode",
        "lon_lowestmode",
        "elev_lowestmode",
        "elev_highestreturn",
        "sensitivity",
        "quality_flag",
        "rh",
    ],
    latlayer: str = "lat_lowestmode",
    lonlayer: str = "lon_lowestmode",
) -> pd.DataFrame:
    """
    Given the absolute path to a directory of GEDI Level 2A h5 files, the
    names of the h5 files, and information about the desired output, ingest
    the h5 files and output a pd.DataFrame containing data for all the valid
    shots within the bounding box.

    The output will have an array-valued column that is designed to be handled
    by append_canopy_metrics and then deleted from the DataFrame.

    Parameters
    ----------
    file_dir : str
        Path to directory containing the h5 files, including a trailing slash
        such that {file_dir}{fname} is a valid path to a file, given fname a
        valid file name.
    file_paths : List[str]
        The names of the h5 files to process.
    bbox : List[float]
        The coordinates of the bounding box, formatted as
        [ul_lat, ul_lon, lr_lat, lr_lon].
    layers : List[str]
        The columns for the output DataFrame.
    latlayer : str
        The name of the latitude layer.
    lonlayer : str
        The name of the longitude layer.

    Returns
    -------
    pd.DataFrame containing the user-specified contents of the h5 files for the
    valid shots within the specified bounding box.
    """
    df = pd.DataFrame()
    for _f_name in file_paths:
        try:
            _f = h5py.File(f"{file_dir}{_f_name}", "r")
            print(f"Processing file {_f_name}")
            [ul_lat, ul_lon, lr_lat, lr_lon] = bbox
            for beam in [
                "BEAM0000",
                "BEAM0001",
                "BEAM0010",
                "BEAM0011",
                "BEAM0101",
                "BEAM0110",
                "BEAM1000",
                "BEAM1011",
            ]:
                tmp_df = pd.DataFrame()
                x = _f[beam][latlayer][()]
                y = _f[beam][lonlayer][()]
                qual = _f[beam]["quality_flag"][()]

                mask = (
                    (qual == 1)
                    & (x <= ul_lat)
                    & (x >= lr_lat)
                    & (y <= lr_lon)
                    & (y >= ul_lon)
                )
                tmp_df["beam"] = [beam] * np.count_nonzero(mask)

                for layer in layers:
                    tmp_df[layer] = _f[beam][layer][()][mask].tolist()

                df = df.append(tmp_df)

        except KeyError as e:
            print(f"Encountered file read error with file {_f_name}")

    return df.reset_index(drop=True)


def _compute_nan_percentile(a: np.ndarray, q: float) -> np.array:
    """This code is taken directly from StackOverflow at:
    https://stackoverflow.com/questions/60015245/numpy-nanpercentile-is-extremely-slow

    For 2d masked array of roughly 10^5 x 100, this performs ~3x faster than
    np.nanpercentile (~10s vs. 3s) and produces results which are identical.

    Would be good to add two tests to verify: (1) the results of this function are
    the same as np.nanpercentile, and (2) that this function takes less time on a
    reasonably sized array, in case of future performance gains in nanpercentile.

    Parameters
    ----------
    a : array_like
        2d array for which to compute a row-wise percentile.
    q : float
        Percentile to compute -- allowed values are [0, 100]

    Returns
    -------
    np.array of the q'th percentile for each row of a. Dimensions of [len(a), 1].
    """
    if q < 0 or q > 100:
        raise ValueError(f"Expected a value between 0 and 100; received {q} instead.")
    mask = (a >= np.nanmin(a)).astype(int)

    count = mask.sum(axis=1)
    groups = np.unique(count)
    groups = groups[groups > 0]

    p = np.zeros((a.shape[0]))
    for g in range(len(groups)):
        pos = np.where(count == groups[g])
        values = a[pos]
        values = np.nan_to_num(values, nan=(np.nanmin(a) - 1))
        values = np.sort(values, axis=1)
        values = values[:, -groups[g] :]
        p[pos] = np.percentile(values, q, axis=1)
    return p


def append_canopy_metrics(df: pd.DataFrame, canopy_threshold: float) -> None:
    """
    This function takes a pd.DataFrame object and a numerical value corresponding
    to the height threshold to consider a return as coming from the forest canopy.
    It extracts the "rh" column from the provided DataFrame as an np.ndarray,
    applies a mask, and computes the relevant canopy metrics which are then
    appended to the provided DataFrame.

    Note: the least bad option for computing these canopy metrics seemed to be
    using np.ma module to work with masked arrays. Not converting out of Pandas is
    untenable due to computation time, and the varying dimension of rows when
    subset to canopy-only observations means np converts the result of applying
    the mask to the 2d array to a 1d array.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame, assumed to be the output of gedi_L2A_to_df, for which
        canopy metrics should be calculated. The provided df must contain a column
        labeled "rh" which is array-valued.
    canopy_threshold : float
        The minimum value for a return to be considered a "canopy" return.

    Side Effects
    ------------
    Modifies the provided pd.DataFrame in-place to add canopy metrics. 

    Returns
    -------
    None
    """
    rh = np.stack(df.rh.to_numpy())
    canopy_returns = np.ma.masked_less(rh, canopy_threshold)

    canopy_max = np.max(canopy_returns, axis=1)
    canopy_min = np.min(canopy_returns, axis=1)
    canopy_std = np.std(canopy_returns, axis=1)
    canopy_avg = np.average(canopy_returns, axis=1)
    dns = canopy_returns.count(axis=1)  # % all returns >= canopy threshold

    canopy_returns = np.ma.filled(canopy_returns, np.nan)
    canopy_p10 = _compute_nan_percentile(canopy_returns, 10)
    canopy_p25 = _compute_nan_percentile(canopy_returns, 25)
    canopy_p50 = _compute_nan_percentile(canopy_returns, 50)
    canopy_p75 = _compute_nan_percentile(canopy_returns, 75)
    canopy_p90 = _compute_nan_percentile(canopy_returns, 90)

    d01 = np.ma.masked_outside(rh, canopy_threshold, 5).count(
        axis=1
    )  # % returns >= canopy, <=5m
    d02 = np.ma.masked_outside(rh, 5, 10).count(axis=1)  # % returns >= 5m, <=10m
    d03 = np.ma.masked_outside(rh, 10, 20).count(axis=1)  # % returns >= 10m, <=20m
    d04 = np.ma.masked_outside(rh, 20, 30).count(axis=1)  # % returns >= 20m, <=30m

    df["canopy_max"] = pd.Series(canopy_max)
    df["canopy_min"] = pd.Series(canopy_min)
    df["canopy_std"] = pd.Series(canopy_std)
    df["canopy_avg"] = pd.Series(canopy_avg)
    df["canopy_p10"] = pd.Series(canopy_p10)
    df["canopy_p25"] = pd.Series(canopy_p25)
    df["canopy_p50"] = pd.Series(canopy_p50)
    df["canopy_p75"] = pd.Series(canopy_p75)
    df["canopy_p90"] = pd.Series(canopy_p90)
    df["dns"] = pd.Series(dns)
    df["d01"] = pd.Series(d01)
    df["d02"] = pd.Series(d02)
    df["d03"] = pd.Series(d03)
    df["d04"] = pd.Series(d04)


def df_to_geojson(df, outfile):
    """
    Convert pandas dataframe to GeoJSON file and save as given file name and path.
    This file type can be useful when working locally in GIS software.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame, assumed to be the output of gedi_L2A_to_df, with or without
        canopy height metrics appended.
    outfile : str
        The location and filename of output json file.

    Returns
    -------
    None
    """
    df["geometry"] = df.apply(
        lambda row: Point(row.lon_lowestmode, row.lat_lowestmode), axis=1
    )
    GeoDF = gp.GeoDataFrame(df)
    GeoDF = GeoDF.drop(columns=["lat_lowestmode", "lon_lowestmode"])
    GeoDF.to_file(outfile, driver="GeoJSON")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--dir",
        help=(
            "The directory containing hd5 files, formatted with a trailing slash,"
            " such that {dir}{fname} is a valid path, for fname a valid file name."
        ),
    )
    parser.add_argument(
        "-o",
        "--outfile",
        help=(
            "The stem of the name of the output file, without file extension, "
            "optional. Default value is 'gedi_output'."
        ),
        default="gedi_output",
    )
    parser.add_argument(
        "-f",
        "--filetype",
        help="The type of file to output. Acceptable formats are: csv, parquet, GeoJSON.",
        default="parquet",
    )
    args = parser.parse_args()

    ul_lat = 43.38
    ul_lon = -124.1
    lr_lat = 42.88
    lr_lon = -123.6
    bbox = [ul_lat, ul_lon, lr_lat, lr_lon]

    files = [
        _f
        for _f in os.listdir(args.dir)
        if os.path.isfile(os.path.join(args.dir, _f)) and _f.endswith(".h5")
    ]

    df = gedi_L2A_to_df(args.dir, files, bbox)
    append_canopy_metrics(df, canopy_threshold=2)
    del df["rh"]
    if args.filetype.lower() == "csv":
        df.to_csv(f"{args.dir}{args.outfile}.csv")
    elif args.filetype.lower() == "parquet":
        df.to_parquet(f"{args.dir}{args.outfile}.parquet.gzip", compression="gzip")
    elif args.filetype.lower() == "geojson":
        df_to_geojson(df, f"{args.dir}{args.outfile}.geojson")
    else:
        raise ValueError(
            f"Received unsupported file type {args.filetype}. Please provide one "
            "of: csv, parquet, or GeoJSON."
        )
