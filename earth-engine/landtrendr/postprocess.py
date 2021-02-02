"""
This file contains an attempt at implementing a python version of the Landtrendr
function getSegmentData. A good deal of code here is taken directly from
Section 6 "Working with Outputs" -- specifically 6.1, 6.2, and 6.3 -- of
the LT-GEE documentation here.

See:
    https://emapr.github.io/LT-GEE/api.html#getsegmentdata
    https://emapr.github.io/LT-GEE/working-with-outputs.html (see 6.1, 6.2, 6.3)
"""

import ee
from typing import List

INDEX_DICT = {
    "NDVI": {"dist_dir": -1, "bands": ["B4", "B3"]},
    "NBR": {"dist_dir": -1, "bands": ["B4", "B7"]},
}


def get_segment_data(lt: ee.Image, index: str, right: bool = False) -> ee.Image:
    """
    Given a Landtrendr output, the index of interest, and a boolean flag
    denoting whether or not to reorient inverted index values, return an ee.Image
    object containing information on the segments during which Landtrendr
    detected losses in forest cover.

    Parameters
    ----------
    lt: ee.Image
        The Landtrendr output as an ee.Image object.
    index: str
        The spectral index for which Landtrendr was run.
    right: boolean
        Whether or not to correct the orientation of the index if it has been
        inverted in the process of preparing the Landtrendr collection (see:
        https://emapr.github.io/LT-GEE/api.html#buildltcollection)

    Returns
    -------
    ee.Image
        An image with information on the loss segments as array-valued pixels.

    Python attempt at implementing:
    https://emapr.github.io/LT-GEE/api.html#getsegmentdata"""
    lt_output = lt.select("LandTrendr")
    vertex_mask = lt_output.arraySlice(0, 3, 4)
    vertices = lt_output.arrayMask(vertex_mask)

    try:
        index_info = INDEX_DICT[index]
    except KeyError:
        if index in ["NDSI", "NDMI", "TCB", "TCG", "TCW", "TCA", "NBR2"]:
            # If users provide a valid spectral index, they should get a more helpful
            # exception explaining the source of the issue than just a random KeyError
            raise NotImplementedError(
                f"The index '{index}' is not currently supported. Supported indices are: "
                + ", ".join(list(INDEX_DICT.keys()))
            )
        else:
            raise RuntimeError(
                f"The value '{index}' was not recognized as a standard spectral index."
            )

    if right:
        dist_dir = index_info["dist_dir"]
    else:
        dist_dir = 1

    left = vertices.arraySlice(1, 0, -1)
    right = vertices.arraySlice(1, 1, None)
    start_year = left.arraySlice(0, 0, 1)
    start_val = left.arraySlice(0, 2, 3).multiply(dist_dir)
    end_year = right.arraySlice(0, 0, 1)
    end_val = right.arraySlice(0, 2, 3).multiply(dist_dir)

    dur = end_year.subtract(start_year)
    mag = end_val.subtract(start_val).multiply(dist_dir)
    rate = mag.divide(dur)
    dsnr = mag.divide(lt.select("rmse"))

    seg_info = (
        ee.Image.cat(
            [start_year.add(1), end_year, start_val, end_val, mag, dur, rate, dsnr]
        )
        .toArray(0)
        .updateMask(vertex_mask.mask())
    )

    # FIXME: add filter on magnitude here to restrict to only loss segments

    return seg_info


def extract_deforestation_events(
    LT_segments: ee.Image, start_year: int, end_year: int, dsnr_threshold: float
) -> ee.Image:
    """
    Given an image with information about loss segments, assumed to be the
    output of get_segment_data, bounds on start and end year, and a threshold
    on the disturbance signal-to-noise ratio (DSNR), filter to only events
    within the years of interest which pass the DSNR threshold.

    Note: the decision to extract the most recent event, rather than the
    selecting the largest or using a different selection mechanism, is made
    because this was written with the goal of identifying deforestation events
    followed by a recovery period.

    Parameters
    ----------
    LT_segments: ee.Image
        Landtrendr segment data, assumed to be the output of get_segment_data
    start_year: int
        The first year to consider for deforestation events.
    end_year: int
        The last year to consider for deforestation events.
    dsnr_threshold: float
        The threshold on the disturbance signal-to-noise ratio (DSNR) for the
        deforestation segments.

    Returns
    -------
    ee.Image
        The input image filtered to the most recent event in each pixel which
        passes the given threshold.
    """
    start_years = LT_segments.arraySlice(0, 0, 1)
    end_years = LT_segments.arraySlice(0, 1, 2)
    dsnr = LT_segments.arraySlice(0, 7, 8)
    mask = (
        start_years.gte(ee.Image(start_year))
        .And(end_years.lte(ee.Image(end_year)))
        .And(dsnr.gte(ee.Image(dsnr_threshold)))
    )

    masked_segments = LT_segments.arrayMask(mask)

    # Extract the most recent segments for each pixel
    # factor of -1 to flip delta, since arraySort is ascending
    sort_by = masked_segments.arraySlice(0, 0, 1).toArray(0).multiply(-1)
    segments_sorted = masked_segments.arraySort(sort_by)
    return segments_sorted.arraySlice(1, 0, 1)


def extract_deforested_regions(
    LT_result: ee.Image,
    index: str,
    start_year: int,
    end_year: int,
    dsnr_threshold: float,
):
    """
    Given the output of Landtrendr as an image, the index of interest, bounds on
    the beginning and end of the period to identify events, and a threshold on
    the DSNR, return a flattened image containing information about the most
    recent deforestation event in each pixel which passes the specified DSNR
    threshold.

    Note: the decision to extract the most recent event, rather than the
    selecting the largest or using a different selection mechanism, is made
    because this was written with the goal of identifying deforestation events
    followed by a recovery period.

    Parameters
    ----------
    LT_segments: ee.Image
        Landtrendr segment data, assumed to be the output of get_segment_data
    index: str
        The spectral index for which Landtrendr was run.
    start_year: int
        The first year to consider for deforestation events.
    end_year: int
        The last year to consider for deforestation events.
    dsnr_threshold: float
        The threshold on the disturbance signal-to-noise ratio (DSNR) for the
        deforestation segments.
    """
    LT_segments = get_segment_data(LT_result, index, True)
    events = extract_deforestation_events(
        LT_segments, start_year, end_year, dsnr_threshold
    )

    flattened_image = ee.Image.cat(
        events.arraySlice(0, 0, 1).arrayProject([1]).arrayFlatten([["yod"]]),
        events.arraySlice(0, 1, 2).arrayProject([1]).arrayFlatten([["endYr"]]),
        events.arraySlice(0, 2, 3).arrayProject([1]).arrayFlatten([["startVal"]]),
        events.arraySlice(0, 3, 4).arrayProject([1]).arrayFlatten([["endVal"]]),
        events.arraySlice(0, 4, 5).arrayProject([1]).arrayFlatten([["mag"]]),
        events.arraySlice(0, 5, 6).arrayProject([1]).arrayFlatten([["dur"]]),
        events.arraySlice(0, 6, 7).arrayProject([1]).arrayFlatten([["rate"]]),
        events.arraySlice(0, 7, 8).arrayProject([1]).arrayFlatten([["dsnr"]]),
    )

    return flattened_image
