# GEDI
This folder is intended for code relating to data from the [GEDI](https://gedi.umd.edu/) mission.
The Level 2A data from GEDI are of particular interest for our work here.
This dataset allows us to measure canopy heights for large swaths of land at approximately 30m resolution.

# GEDI Retrieval
The GEDI mission is a relatively new mission to the story of Earth Observation, and is still currently taking data of the Earth's surface while aboard the International Space Station.
Thus the GEDI data is still in a rudimentary form.
When downloaded, the entire Level 2A dataset available as of 3 February 2021 is nearly 40 TB.
This is too big for many individuals to work with, and time needed to download that much data to an individual machine would be too great for the highly adaptive work we are doing.

We must therefore develop a methodology that can quickly find, retrieve, download, and gather the appropriate data for our purpose.
Here, we present such a methodology that utilizes the NASA LP DAAC GEDI Data Finder service (https://lpdaac.usgs.gov/news/release-gedi-finder-web-service/) and the NASA EarthData Search application (https://earthdata.nasa.gov) to accomplish this task.

## GEDI Finder

The GEDI Finder program (gediFinder.py) builds off the NASA service, the LP DAAC GEDI Finder, and allows for a fast and easy way to determine the appropriate GEDI data for a specific bounding box.

The user supplies the output directory and the bounding box of interest, and the user has the option to supply the GEDI data level and the name of the file created.
If the optional arguments for the GEDI data level and the name of the output file are not supplied, the program uses the default parameters of L2A and granule_list, respectively.

A comma-separated list of each GEDI granule that intersects the bounding box of interest is written to the output file as a .txt file.
The list of granules is used to select the appropriate granules to download in the NASA EarthData Search application.
***To use this list in future steps, the user must open the file and copy the entire contents.***

The program can be run, once the user has navigated to the appropriate directory, as follows:

`python gediFinder.py -d DirectoryPath -b ul_lat,ul_lon,lr_lat,lr_lon -l 2a`

## EarthData Search
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

# GEDI Combine
open safari

navigate to download page in Earthdata Search

open html file (first file listed in download links)

Download first zip file

open Finder
Open README in unzipped file

Create new text file to store zip urls

open terminal

In terminal:

python gediCombine_individual.py -d DirectoryPath -t FilePath -o gedi_output -f csv -b ul_lat,ul_lon,lr_lat,lr_lon
