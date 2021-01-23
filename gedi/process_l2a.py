import argparse
import h5py
import numpy as np
import os
import pandas as pd

from typing import List


def hf5s_to_df(
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
):
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

    out = hf5s_to_df(args.dir, files, bbox)
    out.to_parquet(f"{args.dir}{args.outfile}.parquet.gzip", compression="gzip")
