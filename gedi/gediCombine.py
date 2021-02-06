#!/usr/bin/env python
"""
This program goes through the following process:
    Download GEDI HDF5 files
    Retrieve approproate data from files
    Remove GEDI HDF5 files
    Write data to file
The following layers are retrieved from the raw GEDI data:
    shot_number, lat_lowestmode, lon_lowestmode, elev_lowestmode, elev_highestreturn,
    sensitivity, quality_flag, rh
rh is converted to the following canopy height metrics:
    canopy height max, min, std, avg
    canopy height percentiles 10, 25, 50, 75, 90
    number of canopy height measurements in range h<5m, 5m<h<10m,
        10m<h<20m, and 20m<h<30m

To Run
----------
python gediCombine.py -d DirectoryPath -t FilePath -b ul_lat,ul_lon,lr_lat,lr_lon -o Filename -f Filetype

Arguments
-------
    -d,--dir : str
        The directory containing url txt file, formatted with a trailing slash,
        such that {dir}{fname} is a valid path, for fname a valid file name.
    -t,--textfile : str
        The txt file containing the urls for the zip files, supplied by
        EarthData Search.
    -b,--bbox : str
        The bounding box of the region of interest. In format
        ul_lat,ul_lon,lr_lat,lr_lon
    -o,--outfile : str (optional)
        The stem of the name of the output file, without file extension,
        optional. Default value is 'gedi_output'.
        default="gedi_output"
    -f,--filetype : str (optional)
        The type of file to output. Acceptable formats are: csv, parquet, GeoJSON.
        default="csv"

Outputs
-------
Generates file of input filetype with Level 2B data retrieved from GEDI servers.
"""

import validators
import argparse
import requests
import zipfile
import h5py
import io
import os
import numpy as np
import pandas as pd
import geopandas as gp

from typing import List
from shutil import rmtree
from shapely.geometry import Point

def gedi_L2A_to_df(
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
            _f = h5py.File(f"{_f_name}", "r")
            print(f"Processing file {os.path.basename(_f_name)}")
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

                if np.count_nonzero(mask) == 0:
                    continue
                    print(f"{beam} in {os.path.basename(_f_name)} does not contain any usable data")

                else:
                    tmp_df["beam"] = [beam] * np.count_nonzero(mask)

                    for layer in layers:
                        tmp_df[layer] = _f[beam][layer][()][mask].tolist()

                    _append_canopy_metrics(tmp_df, canopy_threshold=2)
                    del tmp_df["rh"]

                    df = df.append(tmp_df)

        except KeyError as e:
            print(f"Encountered file read error with file {_f_name}")


    return df.reset_index(drop=True)


def _compute_nan_percentile(a: np.ndarray, q: float) -> np.array:
    """
    This code is taken directly from StackOverflow at:
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
    a = np.sort(a, axis =1)
    count = (~np.isnan(a)).sum(axis=1) # count number of non-nans in row
    groups = np.unique(count)     # returns sorted unique values
    groups = groups[groups > 0]   # only returns groups with at least 1 non-nan value\n",

    p = np.zeros((a.shape[0]))
    for group in groups:
        pos = np.where(count == group)
        values = a[pos]
        values = values[:, :group]
        p[pos] = np.percentile(values, q, axis=1)

    return p


def _append_canopy_metrics(df: pd.DataFrame, canopy_threshold: float) -> None:
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

    df["canopy_max"] = pd.Series(np.max(canopy_returns, axis=1))
    df["canopy_min"] = pd.Series(np.min(canopy_returns, axis=1))
    df["canopy_std"] = pd.Series(np.std(canopy_returns, axis=1))
    df["canopy_avg"] = pd.Series(np.average(canopy_returns, axis=1))
    df["dns"] = pd.Series(
        canopy_returns.count(axis=1)
    )  # % all returns >= canopy threshold

    canopy_returns = np.ma.filled(canopy_returns, np.nan)
    df["canopy_p10"] = pd.Series(_compute_nan_percentile(canopy_returns, 10))
    df["canopy_p25"] = pd.Series(_compute_nan_percentile(canopy_returns, 25))
    df["canopy_p50"] = pd.Series(_compute_nan_percentile(canopy_returns, 50))
    df["canopy_p75"] = pd.Series(_compute_nan_percentile(canopy_returns, 75))
    df["canopy_p90"] = pd.Series(_compute_nan_percentile(canopy_returns, 90))

    df["d01"] = pd.Series(
        np.ma.masked_outside(rh, canopy_threshold, 5).count(axis=1)
    )  # % returns >= canopy, <=5m
    df["d02"] = pd.Series(
        np.ma.masked_outside(rh, 5, 10).count(axis=1)
    )  # % >= 5m, <=10m
    df["d03"] = pd.Series(
        np.ma.masked_outside(rh, 10, 20).count(axis=1)
    )  # % >= 10m, <=20m
    df["d04"] = pd.Series(
        np.ma.masked_outside(rh, 20, 30).count(axis=1)
    )  # % >= 20m, <=30m


def df_to_geojson(df : pd.DataFrame, outfile : str) -> None:
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
    Side Effects
    -------
    Writes dataframe to geojson filetype
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

def download_url(url : str, dir : str, chunk_size : int = 128) -> None:
    """
    Download the zip files generated by NASA EarthData Search.
    Parameters
    ----------
    url : str
        URL used to download data zip package
    dir : str
        Directory used to store the zip file and unzipped contents
    chunk_size : int
        Determines the size of each chunk written to file during data streaming
    Side Effects
    -------
    Downloads and unpacks the zip file from the provide url
    Returns
    -------
    None
    """
    filepath = os.path.join(dir, "granuleData.zip")
    r = requests.get(url, stream = True)

    if r.status_code == requests.codes.ok:
        print(f"Downloading files from {url}")

        # Download zip file and save to dir
        with open(filepath, 'wb') as fd:
            for chunk in r.iter_content(chunk_size = chunk_size):
                fd.write(chunk)

        print(f"Unzipping files")
        # Unzip contents
        with zipfile.ZipFile(filepath, 'r') as zipObj:
            # Extract all the contents of zip file in current directory
            zipObj.extractall(path = dir)

        # Remove zip file
        rmtree(filepath)

        return True

    else:
        print(
            f'Error {r.status_code} has occurred.\n'
            f'{url} cannot be downloaded at this time.'
        )

        return False

if __name__ == "__main__":
    # things I would like to see: displays 'arg help' if no arguments are given, docstrings with proper usage
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--dir",
        help=(
            "The directory containing url txt file supplied by the"
            "--textfile argument"
        ),
    )
    parser.add_argument(
        "-t",
        "--textfile",
        help=(
            "The txt file containing the urls for the zip files, supplied by"
            "EarthData Search."
        ),
    )
    parser.add_argument(
        "-b",
        "--bbox",
        help=(
            "The bounding box of the region of interest. In format"
            "ul_lat,ul_lon,lr_lat,lr_lon"
        )
    )
    parser.add_argument(
        "-o",
        "--outfile",
        help=(
            "The stem of the name of the output file, without file extension,"
            "optional. Default value is 'gedi_output'."
        ),
        default="gedi_output",
    )
    parser.add_argument(
        "-f",
        "--filetype",
        help=(
            "The type of file to output. Acceptable formats are: csv,"
            "parquet, GeoJSON. Default value is csv."
        ),
        default="csv",
    )
    args = parser.parse_args()

    print("------------------------------------------")

    bbox = [float(b) for b in args.bbox.split(',')]

    df = pd.DataFrame()

    with open(str(args.textfile), 'r') as texturls:
        for url in texturls:
            if validators.url(url):

                status = download_url(url.rstrip('\n'), args.dir)
                if not status:
                    print("------------------------------------------")
                    continue
                print("          ----------------------          ")
                # Make list of filepaths
                filepaths = [
                    os.path.join(root, file)
                    for root, dir, files in os.walk(args.dir, topdown = False)
                    for file in files
                    if file.endswith('.h5')
                ]

                tmp_df = gedi_L2A_to_df(filepaths, bbox = bbox)
                print("          ----------------------          ")
                # append data to dataframe
                df = df.append(tmp_df)
                print(f"Appended {len(tmp_df)} lines to dataframe; Dataframe has {len(df)} lines")

                # Delete hdf5 files
                for filepath in filepaths:
                    rmtree(os.path.dirname(filepath))

                print("------------------------------------------")

    if df.empty:
        print("DataFrame is empty. Not writing data to file")
        print("------------------------------------------")
    else:
        if args.filetype.lower() == "csv":
            filename = os.path.join(args.dir, args.outfile + ".csv")
            print(f'Writing to file {filename}')
            df.to_csv(filename, index=False)
        elif args.filetype.lower() == "parquet":
            filename = os.path.join(args.dir, args.outfile + ".parquet.gzip")
            print(f'Writing to file {filename}')
            df.to_parquet(filename, compression="gzip")
        elif args.filetype.lower() == "geojson":
            filename = os.path.join(args.dir, args.outfile + ".geojson")
            print(f'Writing to file {filename}')
            df_to_geojson(df, filename)
        else:
            raise ValueError(
                f"Received unsupported file type {args.filetype}. Please provide one of: csv, parquet, or GeoJSON."
            )
        print("Job Complete!")
        print("------------------------------------------")
