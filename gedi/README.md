# GEDI
This folder is intended for code relating to data from the [GEDI](https://gedi.umd.edu/) mission.
The Level 2A data from GEDI are of particular interest for our work here.
This dataset allows us to measure canopy heights for large swaths of land at approximately 30m resolution.

## GEDI Retrieval
The GEDI mission is a relatively new mission to the story of Earth Observation, and is still currently taking data of the Earth's surface while aboard the International Space Station.
Thus the GEDI data is still in a rudimentary form.
When downloaded, the entire Level 2A dataset available as of 3 February 2021 is nearly 40 TB.
This is too big for many individuals to work with on their personal machines, and time needed to download that much data would be too great for the highly adaptive workflow we are implement.

We must therefore develop a methodology that can quickly find, retrieve, download, and gather the appropriate data for our purpose.
Here, we present such a methodology that utilizes the [NASA LP DAAC GEDI Data Finder service](https://lpdaac.usgs.gov/news/release-gedi-finder-web-service/) and the [NASA EarthData Search application](https://earthdata.nasa.gov/search) to accomplish this task.

## Dependencies
* `io`
* `os`
* `h5py`
* `numpy`
* `pandas`
* `zipfile`
* `argparse`
* `requests`
* `geopandas `
* `List from typing`
* `remtree from shutil`
* `Point from shapely.geometry`
* `urlencode from urllib.parse`

### GEDI Finder

The GEDI Finder program (gediFinder.py) builds off the NASA service, the LP DAAC GEDI Finder, and allows for a fast and easy way to determine the appropriate GEDI data for a specific bounding box.

The user supplies the output directory and the bounding box of interest, and the user has the option to supply the GEDI data level and the name of the file created.
If the optional arguments for the GEDI data level and the name of the output file are not supplied, the program uses the default parameters of L2A and granule_list, respectively.

A comma-separated list of each GEDI granule that intersects the bounding box of interest is written to the output file as a .txt file.
The list of granules is used to select the appropriate granules to download in the NASA EarthData Search application.
**To use this list in future steps, the user must open the file and copy the entire contents.**

#### To Run
`python gediFinder.py -d DirectoryPath -b ul_lat,ul_lon,lr_lat,lr_lon -l 2a` ([source](gediFinder.py))

#### Arguments
- `-d,--dir` : The directory containing url txt file, formatted with a trailing slash, such that {dir}{fname} is a valid path, for fname a valid file name.
- `-b, --bbox` : The bounding box of the region of interest. In format ul_lat,ul_lon,lr_lat,lr_lon.
- `-l,--level` *(optional)* : The data product level of interest. Acceptable answers at this time are 1B, 2A, or 2B with default of 2A. The default argument if none is given is *2A*.
- `-o,--outfile` *(optional)* : The stem of the name of the output file, without file extension, optional. The default argument if none is given is *granule_list*.

#### Output
Text file with a comma-separated list of GEDI granules that intersect user-defined bounding box

### EarthData Search

Pages 2-4 in the [GEDI Spatial Querying and Subsetting Quick Guide](https://lpdaac.usgs.gov/documents/635/GEDI_Quick_Guide.pdf) provides a great overview of the process we implement in relation to data collection from [NASA EarthData Search application](https://earthdata.nasa.gov/search).
The following is pasted **directly** from the [GEDI Spatial Querying and Subsetting Quick Guide](https://lpdaac.usgs.gov/documents/635/GEDI_Quick_Guide.pdf). Some modifications have been made for readability and context and are *emphasized*.

> 1. **Access Earthdata Search**
> 
> After *obtaining a comma-separated list of GEDI granules with GEDI Finder* , open [NASA Earthdata Search](https://search.earthdata.nasa.gov/). Sign in with Earthdata Login credentials or [register](https://urs.earthdata.nasa.gov/users/new) for a new account.
>
> Note: Currently there are no spatial searching capabilities for the GEDI Version 1 datasets in Earthdata Search.
>
> 2. **Search for Dataset**
>
> Search for a collection by entering the dataset short name *(e.g. GEDI02_A)* into the search box then select the desired product from the list of matching collections.
> All available granules for the product will be included in the list of matching granules.
>
> 3. **Search for Granules**
>
> Copy the list of comma-separated granule IDs *obtained with GEDI Finder* and paste it into the Granule Search box in Earthdata Search. Use the Enter key to initiate the search.
>
> 4. **Select spatial and/or layer parameters for GEDI granules**
>
> Click on the green Download All button to open the download and order menu. Under “Select Data Access Method,” select Customize.
>
> To set up the parameters for clipping out a smaller area of the granule, scroll down to the Spatial Subsetting section.
> Check the box next to Click to Enable and enter coordinates of the bounding box for the ROI.
>
> To select specific science dataset layers, scroll down to the Band Subsetting section.
> Expand the directories and select the desired layers.
> Additional information for each of the data layers can be found on the [GEDI01_B](https://doi.org/10.5067/GEDI/GEDI01_B.001), [GEDI02_A](https://doi.org/10.5067/GEDI/GEDI02_A.001), or [GEDI02_B](https://doi.org/10.5067/GEDI/GEDI02_B.001) Digital Object Identifier (DOI) landing page.
>
> 5. **Place Order**
>
> After the desired parameters for spatial and/or layer subsetting have been selected, click Done to complete the custom order form then click Download Data to initiate the order.
> When the data request is submitted, an order confirmation email is sent to the email address associated with the Earthdata login credentials or specified in the custom order form.
>
> 6. **Retrieve Data**
>
> A status update email for the data processing request will be delivered when the order has completed. The order completion email contains URLs for accessing the data outputs.
> Please note that the URLs have an expiration date and are only valid for one week.

There is another step we implement to prepare the data for download and extraction with GEDI Combine.

7. **Get List of Zip File URLs**

Copy the url ending with `.zip?1` and paste into the web browser of your choosing.
The ZIP file should begin downloading.
Once the file has completed downloading, unzip the file and access the README file in the unzipped folder.
This README file will be used as the `--textfile` argument when running the GEDI Combine script.

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
`python gediCombine_individual.py -d DirectoryPath -t FilePath -b ul_lat,ul_lon,lr_lat,lr_lon -o gedi_output -f csv` ([source](gediCombine.py))

#### Arguments
- `-d,--dir` : The directory containing url txt file, formatted with a trailing slash, such that {dir}{fname} is a valid path, for fname a valid file name.
- `-t,--textfile` : The file path for the txt file containing the downloaded urls of the zip files, supplied by EarthData Search.
- `-b,--bbox` : The bounding box of the region of interest. In format ul_lat,ul_lon,lr_lat,lr_lon
- `-o,--outfile` *(optional)* : The stem of the name of the output file, without file extension, optional. The default argument if none is given is *gedi_output*.
- `-f,--filetype` *(optional)* : The type of file to output. Acceptable formats are: csv, parquet, GeoJSON. The default argument if none is given is *csv*.

#### Output
Generates file of input filetype with Level 2B data retrieved from GEDI servers.
