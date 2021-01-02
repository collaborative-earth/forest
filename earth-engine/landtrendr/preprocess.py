# -*- coding: utf-8 -*-
"""
This file contains an attempt at implementing a python version of the Landtrendr
function buildSRcollection.

See:
    https://emapr.github.io/LT-GEE/api.html#buildsrcollection
    https://www.mdpi.com/2072-4292/10/5/691/htm, in particular section 2.3.2

Additionally, a good deal of inspiration, and in some cases code itself, taken
from Justin Braaten's work at:
https://github.com/eMapR/LT-GEE/blob/master/scripts/python/lt_gee_bap_test.py
"""

import ee
from typing import List

INDEX_DICT = {
    "NDVI": {"dist_dir": -1, "bands": ["B4", "B3"]},
    "NBR": {"dist_dir": -1, "bands": ["B4", "B7"]},
}


def _extract_and_append_date(image: ee.Image, input_list: ee.List) -> ee.List:
    """Given an ee.Image and an ee.List, append the image's date to the list."""
    date = image.date()
    return ee.List(input_list).add(ee.Date(date))


def _create_yearly_list(collection: ee.ImageCollection) -> ee.List:
    """Given an ee.ImageCollection, return an ee.List containing all the (unique)
    years present in the collection."""
    dates = collection.iterate(_extract_and_append_date, ee.List([]))

    years = ee.List(dates).map(lambda date: ee.Date(date).get("year")).distinct().sort()

    return years


def _extract_medoid_image(
    year: int,
    collection: ee.ImageCollection,
    start_day: str = "06-20",
    end_day: str = "09-10",
) -> ee.Image:
    """Given a year of interest, an ee.ImageCollection, and boundaries of start
    and end days, return an ee.Image which is the medoid image for the year in
    question. Distance calculated using the standard Euclidean norm across all
    6 TM-equivalent bands. Question: is it possible to do better, for the purposes
    of a deforestation analysis, by applying a higher weight to NIR and SWIR bands?

    Parameters
    ----------
    year: int
      The year for which the medoid should be calculated.
    collection: ee.ImageCollection
      The collection whose medoid should be calculated.
    start_day: str
      The first day, inclusive, to consider in calculating the medoid. Formatted
      as 'mm-dd'.
    end_day: str
      The last day, inclusive, to consider in calculating the medoid. Formatted as
      'mm-dd'.

    Returns
    -------
    ee.Image
      An ee.Image containing the pixel-wise medoid for the year in question.
    """
    start_m, start_d = start_day.split("-")
    end_m, end_d = end_day.split("-")

    start_date = ee.Date.fromYMD(ee.Number(year), int(start_m), int(start_d))
    end_date = ee.Date.fromYMD(ee.Number(year), int(end_m), int(end_d)).advance(
        1, "day"
    )
    filtered_collection = collection.filterDate(start_date, end_date)

    # At this point in LT-GEE implementation, ee.Algorithms.If is used to check
    # number of input images. However, checking using .gt() appears to not work
    # with Algorithms.If since it returns a numeric value. For now, punt on
    # figuring this out and just assume we have a non-empty collection at this point.
    # https://github.com/eMapR/LT-GEE/blob/b0e92a0c198bdd1a794e1e9b8f4db8fc7fa06054/scripts/python/lt_gee_bap_test.py#L104

    median = filtered_collection.median()

    def _euclidean_distance(image: ee.Image) -> ee.Image:
        distance = ee.Image(image).subtract(median).pow(ee.Image.constant(2))
        return distance.reduce("sum").addBands(image)

    distance_from_median = filtered_collection.map(_euclidean_distance)
    return (
        ee.ImageCollection(distance_from_median)
        .reduce(ee.Reducer.min(7))
        .set("system:time_start", ee.Date.fromYMD(year, 1, 1).millis())
    )


def _generate_medoid_collection(collection, start_day, end_day):
    """Given an ee.ImageCollection and bounds on the start and end days, compute
    an ee.ImageCollection which contains a medoid image for each year present in
    the input collection.

    Parameters
    ----------
    collection: ee.ImageCollection
      The collection whose medoid should be calculated.
    start_day: str
      The first day, inclusive, to consider in calculating the medoid. Formatted
      as 'mm-dd'.
    end_day: str
      The last day, inclusive, to consider in calculating the medoid. Formatted as
      'mm-dd'.

    Returns
    -------
    ee.ImageCollection
      A collection of yearly medoid images for the provided collection.
    """

    years = _create_yearly_list(collection)

    def _extract_medoid(year):
        return _extract_medoid_image(year, collection, start_day, end_day)

    images = years.map(_extract_medoid)
    return ee.ImageCollection.fromImages(images)


def _mask_landsat_sr(image: ee.Image) -> ee.Image:
    """Apply a mask to a Landsat image to filter out water, cloud, snow, and cloud
    shadow pixels."""
    qa_band = image.select("pixel_qa")
    # Bits 2, 3, 4, and 5 of pixel_qa band of Landsat are water, cloud shadow, snow,
    # and cloud, respectively. Define bitmasks for these entries below:
    water_bit_msk = 1 << 2
    cloud_shadow_bit_msk = 1 << 3
    snow_bit_msk = 1 << 4
    cloud_bit_msk = 1 << 5

    qa_mask = (
        qa_band.bitwiseAnd(water_bit_msk)
        .eq(0)
        .And(qa_band.bitwiseAnd(cloud_shadow_bit_msk).eq(0))
        .And(qa_band.bitwiseAnd(snow_bit_msk).eq(0))
        .And(qa_band.bitwiseAnd(cloud_bit_msk).eq(0))
    )

    return image.updateMask(qa_mask)


def _prepare_images(
    image: ee.Image, input_bands: List[str], output_bands: List[str]
) -> ee.Image:
    """Takes an ee.Image object and a list of input and output bands; this function
    resamples the image using bilinear resampling, applies a QA mask, and returns
    an ee.Image with the output bands selected and with the system:time_start
    field set from input image.

    Intended to be used via partial execution for TM and OLI collections.

    Parameters
    ----------
    image: ee.Image
      The image to prepare.
    input_bands: List[str]
      The bands to select from the image.
    output_bands: List[str]
      The labels for the selected bands in the output image.

    Returns
    -------
    ee.Image
      The input image, resampled, with QA mask applied, and with bands renamed.
    """

    resampled_image = image.resample("bilinear").set(
        "system:time_start", image.get("system:time_start")
    )

    return _mask_landsat_sr(resampled_image).select(input_bands, output_bands)


def _build_TM_collection(
    sensor: str,
    aoi: ee.Geometry,
    start_year: int = 1985,
    start_day: int = "06-20",
    end_year: int = 2020,
    end_day: int = "09-10",
) -> ee.ImageCollection:
    """Given the sensor, area of interest, and date boundaries, return a collection
    of TM (or ETM+) Landsat images. Intended for use on Landsat 5 and Landsat 7
    images.

    Parameters
    ----------
    sensor: str
      The sensor to use -- expects one of 'LT05' or 'LE07'.
    aoi: ee.Geometry
      The area of interest for the collection. This will be used in a filterBounds
      call on the collection to reduce size.
    start_year: int
      The first year (inclusive) to get data.
    start_day: str
      The first day (inclusive) to get data. Formatted as 'mm-dd'.
    end_year: int
      The last year (inclusive) to get data.
    end_day: str
      The last day (inclusive) to get data. Formatted as 'mm-dd'.

    Returns
    -------
    ee.ImageCollection
      The filtered collection.
    """

    def _prepare_TM(image: ee.Image) -> ee.Image:
        return _prepare_images(
            image=image,
            input_bands=["B1", "B2", "B3", "B4", "B5", "B7"],
            output_bands=["B1", "B2", "B3", "B4", "B5", "B7"],
        )

    collection = (
        ee.ImageCollection("LANDSAT/" + sensor + "/C01/T1_SR")
        .filterBounds(aoi)
        .filterDate(
            ee.Date(str(start_year) + "-" + start_day),
            ee.Date(str(end_year) + "-" + end_day).advance(1, "day"),
        )
    )
    return collection.map(_prepare_TM)


def _build_OLI_collection(
    sensor: str,
    aoi: ee.Geometry,
    start_year: int = 1985,
    start_day: int = "06-20",
    end_year: int = 2020,
    end_day: int = "09-10",
) -> ee.ImageCollection:
    """Given the sensor, area of interest, and date boundaries, return a collection
    of TM-equivalent Landsat images from an OLI Landsat collection. Intended for
    use on Landsat 8 images.

    This function applies a linear transformation to harmonize Landsat 7 (ETM) and
    Landsat 8 (OLI) images. Transformation developed by Roy et al. and implemented
    by Justin Braaten at:
    https://github.com/eMapR/LT-GEE/blob/master/scripts/python/lt_gee_bap_test.py#L60

    Parameters
    ----------
    sensor: str
      The sensor to use -- expects 'LC08'.
    aoi: ee.Geometry
      The area of interest for the collection. This will be used in a filterBounds
      call on the collection to reduce size.
    start_year: int
      The first year (inclusive) to get data.
    start_day: str
      The first day (inclusive) to get data. Formatted as 'mm-dd'.
    end_year: int
      The last year (inclusive) to get data.
    end_day: str
      The last day (inclusive) to get data. Formatted as 'mm-dd'.

    Returns
    -------
    ee.ImageCollection
      The filtered collection with OLI bands scaled and renamed to TM-equivalents.
    """

    def _harmonization_Roy(image: ee.Image) -> ee.Image:
        """Taken verbatim from Justin Braaten's implementation at:
        https://github.com/eMapR/LT-GEE/blob/b0e92a0c198bdd1a794e1e9b8f4db8fc7fa06054/scripts/python/lt_gee_bap_test.py#L60"""
        slopes = ee.Image.constant([0.9785, 0.9542, 0.9825, 1.0073, 1.0171, 0.9949])
        intercepts = ee.Image.constant(
            [-0.0095, -0.0016, -0.0022, -0.0021, -0.0030, 0.0029]
        )

        return (
            image.subtract(intercepts.multiply(10000))
            .divide(slopes)
            .toShort()
            .set("system:time_start", image.get("system:time_start"))
        )

    def _prepare_OLI(image: ee.Image) -> ee.Image:
        return _prepare_images(
            image=image,
            input_bands=["B2", "B3", "B4", "B5", "B6", "B7"],
            output_bands=["B1", "B2", "B3", "B4", "B5", "B7"],
        )

    collection = (
        ee.ImageCollection("LANDSAT/" + sensor + "/C01/T1_SR")
        .filterBounds(aoi)
        .filterDate(
            ee.Date(str(start_year) + "-" + start_day),
            ee.Date(str(end_year) + "-" + end_day).advance(1, "day"),
        )
    )
    return collection.map(_prepare_OLI).map(_harmonization_Roy)


def _build_combined_Landsat(
    aoi: ee.Geometry,
    start_year: int = 1985,
    start_day: int = "06-20",
    end_year: int = 2020,
    end_day: int = "09-10",
) -> ee.ImageCollection:
    """
    Given an area of interest and date bounds, return a collection containing
    Landsat 5, 7, and 8 images. A linear rescaling is applied to Landsat 8 bands,
    which are from the Operational Land Imager (OLI) instrument, to convert them
    to Thematic Mapper-equivalent values.

    Parameters
    ----------
    aoi: ee.Geometry
      The area of interest for the collection.
    start_year: int
      The first year (inclusive) to get data.
    start_day: str
      The first day (inclusive) to get data. Formatted as 'mm-dd'.
    end_year: int
      The last year (inclusive) to get data.
    end_day: str
      The last day (inclusive) to get data. Formatted as 'mm-dd'.

    Returns
    -------
    ee.ImageCollection
      The TM-equivalent bands from Landsat 5, 7, and 8 for the time period and
      region of interest.
    """
    landsat5 = _build_TM_collection(
        sensor="LT05",
        aoi=aoi,
        start_year=start_year,
        start_day=start_day,
        end_year=end_year,
        end_day=end_day,
    )

    landsat7 = _build_TM_collection(
        sensor="LE07",
        aoi=aoi,
        start_year=start_year,
        start_day=start_day,
        end_year=end_year,
        end_day=end_day,
    )

    landsat8 = _build_OLI_collection(
        sensor="LC08",
        aoi=aoi,
        start_year=start_year,
        start_day=start_day,
        end_year=end_year,
        end_day=end_day,
    )

    return ee.ImageCollection(landsat5.merge(landsat7).merge(landsat8))


def build_SR_collection(
    aoi: ee.Geometry, start_year: int, start_day: str, end_year: int, end_day: str
) -> ee.ImageCollection:
    """
    Given an area of interest and date bounds, return a collection containing a
    yearly medoid for each image in the date range using Landsat 5, 7, and 8
    images.

    Parameters
    ----------
    aoi: ee.Geometry
      The area of interest for the collection.
    start_year: int
      The first year (inclusive) to get data.
    start_day: str
      The first day (inclusive) to get data. Formatted as 'mm-dd'.
    end_year: int
      The last year (inclusive) to get data.
    end_day: str
      The last day (inclusive) to get data. Formatted as 'mm-dd'.

    Returns
    -------
    ee.ImageCollection
      The collection of yearly medoid images.
    """

    combined_landsat = _build_combined_Landsat(
        aoi, start_year, start_day, end_year, end_day
    )
    return _generate_medoid_collection(combined_landsat, start_day, end_day).select(
        [1, 2, 3, 4, 5, 6], ["B1", "B2", "B3", "B4", "B5", "B7"]
    )


def build_LT_collection(
    collection: ee.ImageCollection, index: str, ftv_list: List[str]
) -> ee.ImageCollection:
    """
    Given a surface reflectance collection produced by build_SR_collection,
    the spectral index of interest, and a list of bands to include, produce
    a collection for Landtrendr.

    The first band will be the index of interest, scaled so that an increase
    in the band value indicates vegetation loss.

    Parameters
    ----------
    collection: ee.ImageCollection
        The collection to prepare for Landtrendr.
    index: str
        The spectral index to use. Supported values are 'NDVI' and 'NBR'.
    ftv_list: List[str]
        Additional bands to include in the collection.
    """
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

    dist_dir = index_info["dist_dir"]
    index_bands = index_info["bands"]
    ftv_bands = ["ftv_" + band for band in ftv_list]

    # This function should support a spectral index as a FTV, but a clever way to
    # do this without mixing client- and server-side functions currently eludes me,
    # so I am going to skip it for now.
    def _format_images(image):
        idx = (
            image.normalizedDifference(index_bands)
            .rename(index)
            .multiply(dist_dir * 1000)
        )
        ftv_values = image.select(ftv_list, ftv_bands)
        return idx.addBands(ftv_values).set(
            "system:time_start", image.get("system:time_start")
        )

    return collection.map(_format_images)
