"""
This script is meant to create a GediFinder URL and get the corresponding list of granules within a
user-defined bounding box. This list can then be used in the Earthdata Search Tool to pull data from
within a bounding box.

To Run
----------
python gediFinder.py -d DirectoryPath -b ul_lat,ul_lon,lr_lat,lr_lon -l level -o granule_list

Arguments
-------
    -d,--dir : str
        The directory containing url txt file, formatted with a trailing slash,
        such that {dir}{fname} is a valid path, for fname a valid file name.
    -b, --bbox : str
        The bounding box of the region of interest. In format
        ul_lat,ul_lon,lr_lat,lr_lon
    -l,--level : str (optional)
        The data product level of interest. Acceptable answers at this time
        are 1B, 2A, or 2B with default of 2A
        default = 2A
    -o,--outfile : str (optional)
        The stem of the name of the output file, without file extension,
        optional. Default value is 'gedi_output'.
        default = granule_list

Outputs
-------
Writes granule list to a txt file in directory
"""

import requests
import argparse

from urllib.parse import urlencode

def gediFinder(
    level: str,
    bbox: str,
    version: str = "001",
    output: str = "json",
    lpdaac: str = "https://lpdaacsvc.cr.usgs.gov/services/gedifinder",
) -> str:
    """
    "Description of func"
    Parameters
    ----------
    level : str
        "description of parameter"
    version : str

    bbox : List[float]

    output : str

    Returns
    -------
    str of all HDF5 granules separated by commas
    """

    payload = {
        'product': f'{level}',
        'version': f'{version}',
        'bbox':    f'{bbox}',
        'output':  f'{output}'
    }
    payload_str = urlencode(payload, safe=',')

    r = requests.get(lpdaac, params = payload_str)
    if r.status_code == requests.codes.ok:
        print('Success!')

        granules = [g.split('/')[-1] for g in r.json()['data']] # take filename from url
        return ','.join(granules)

    else:
        print(f'Error {r.status_code} has occurred.')

        error = str(
            f'URL below failed to retrieve GEDI data. '
            f'Error {r.status_code} has occurred. \n {r.url}'
        )
        return error

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--dir",
        help=(
            "The directory containing url txt file, formatted with a trailing slash,"
            " such that {dir}{fname} is a valid path, for fname a valid file name."
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
        "-l",
        "--level",
        help=(
            "The data product level of interest. Acceptable answers at this time"
            "are 1B, 2A, or 2B with default of 2A"
        ),
        default = "2A" # Pacific Northwest
    )
    parser.add_argument(
        "-o",
        "--outfile",
        help=(
            "The stem of the name of the output file, without file extension, "
            "optional. Default value is 'gedi_output'."
        ),
        default="granule_list",
    )
    args = parser.parse_args()

    if args.level.upper() == '1B':
        level = 'GEDI01_B'
    elif args.level.upper() == '2A':
        level = 'GEDI02_A'
    elif args.level.upper() == '2B':
        level = 'GEDI02_B'
    else:
        raise ValueError(
            f"Recieved unsupported data level {args.level}. Please provide 1B, 2A, or 2B"
        )

    with open(os.path.join(args.dir, args.outfile + ".txt"), 'w+') as file:
        file.write(gediFinder(level, args.bbox))
