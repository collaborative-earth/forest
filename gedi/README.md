# GEDI
This folder is intended for code relating to data from the [GEDI](https://gedi.umd.edu/) mission.
The Level 2A data from GEDI are of particular interest for our work here.
This dataset allows us to measure canopy heights for large swaths of land at approximately 30m resolution.

## GEDI Retrieval
The GEDI mission is a relatively new mission to the story of Earth Observation, and is still currently taking data of the Earth's surface while aboard the International Space Station.
Thus the GEDI data is still in a rudimentary form.
When downloaded, the entire Level 2A dataset available as of 3 February 2021 is nearly 40 TB.
This is too big for many individuals to work with, and time needed to download that much data to an individual machine would be too great for the highly adaptive work we are doing.

We must therefore develop a methodology that can quickly find, retrieve, download, and gather the appropriate data for our purpose.
Here, we present such a methodology that utilizes the [NASA LP DAAC GEDI Data Finder service](https://lpdaac.usgs.gov/news/release-gedi-finder-web-service/) and the [NASA EarthData Search application](https://earthdata.nasa.gov/search) to accomplish this task.

### GEDI Finder

The GEDI Finder program (gediFinder.py) builds off the NASA service, the LP DAAC GEDI Finder, and allows for a fast and easy way to determine the appropriate GEDI data for a specific bounding box.

The user supplies the output directory and the bounding box of interest, and the user has the option to supply the GEDI data level and the name of the file created.
If the optional arguments for the GEDI data level and the name of the output file are not supplied, the program uses the default parameters of L2A and granule_list, respectively.

A comma-separated list of each GEDI granule that intersects the bounding box of interest is written to the output file as a .txt file.
The list of granules is used to select the appropriate granules to download in the NASA EarthData Search application.
***To use this list in future steps, the user must open the file and copy the entire contents.***

#### To Run
`python gediFinder.py -d DirectoryPath -b ul_lat,ul_lon,lr_lat,lr_lon -l 2a` [source](gediFinder.py)

#### Arguments
1. ***-d,--dir*** : The directory containing url txt file, formatted with a trailing slash, such that {dir}{fname} is a valid path, for fname a valid file name.
2. ***-b, --bbox*** : The bounding box of the region of interest. In format ul_lat,ul_lon,lr_lat,lr_lon.
3. ***-l,--level*** *(optional)* : The data product level of interest. Acceptable answers at this time are 1B, 2A, or 2B with default of 2A. The default argument if none is given is *2A*.
4. ***-o,--outfile*** *(optional)* : The stem of the name of the output file, without file extension, optional. The default argument if none is given is *granule_list*.

#### Output
Text file with a comma-separated list of GEDI granules that intersect user-defined bounding box

### EarthData Search
open safari

go to https://search.earthdata.nasa.gov/search

Search collections for gedi 2a

Click on GEDI L2A Elevation and Height Metrics Data Global Footprint Level V001

Paste granule list in granule search on left side and press enter

Click download all button

click edit options on left side

Select customize

Select "Click to enable" in spatial subsetting"

Enter in appropriate bounds for the boundign box
	North -> ul_lat
	West  -> ul_lon
	East  -> lr_lon
	South -> lr_lat

Click Done

Click Download Data

Wait until data has been processed by Nasa. This could take anywhere from a few minutes to multiple days depending on the size of the bounding box and other variables on the server side.

### GEDI Combine
The NASA EarthData Search will collect, clip, and process the GEDI granules, creating a number of zip files with the processed data to download.
The gediCombine program we present here takes the list of urls necessary to download the zip files and extracts the data from the files after downloading them.

This program cycles through the list of urls supplied, conducting the following operations to extract the data.
* Download zip file and unzip contents
* Extracts useful data from files
* Delete HDF5 files
* Write data to a pandas DataFrame

After each zip file has been processed and deleted, the DataFrame is written to a csv, parquet, or GeoJSON file, depending on inputs from the user.

#### To Run
`python gediCombine_individual.py -d DirectoryPath -t FilePath -o gedi_output -f csv -b ul_lat,ul_lon,lr_lat,lr_lon` [source](gediCombine.py)

#### Arguments
1. ***-d,--dir*** : The directory containing url txt file, formatted with a trailing slash, such that {dir}{fname} is a valid path, for fname a valid file name.
2. ***-t,--textfile*** : The txt file containing the urls for the zip files, supplied by EarthData Search.
3. ***-b,--bbox*** : The bounding box of the region of interest. In format ul_lat,ul_lon,lr_lat,lr_lon
4. ***-o,--outfile*** *(optional)* : The stem of the name of the output file, without file extension, optional. The default argument if none is given is *gedi_output*.
5. ***-f,--filetype*** *(optional)* : The type of file to output. Acceptable formats are: csv, parquet, GeoJSON. The default argument if none is given is *csv*.

#### Output
Generates file of input filetype with Level 2B data retrieved from GEDI servers.
