"""
This script is meant to create a GediFinder URL and get the corresponding list of granules within a
user-defined bounding box. This list can then be used in the Earthdata Search Tool to pull data from
within a bounding box.
"""

## Import necessary packages

# Use requests package to retreive list of files from GEDI Finder URL
import requests

## Define bounding box and other variables

### Bounding box variables
# Pacific Northwest bbox
ul_lat = 44.75
lr_lat = 44.25
ul_lon = -122.25
lr_lon = -122.75

### Constant values

# Server url for LP DAAC which stores GEDI data
lpdaac = 'https://lpdaacsvc.cr.usgs.gov/services/gedifinder'

# Different levels of GEDI data currently available to the public
productLevel1B = 'GEDI01_B'
productLevel2A = 'GEDI02_A'
productLevel2B = 'GEDI02_B'

# Image verison number
version = '001'

# Create bounding box string for url
bbox = ','.join(map(str, [ul_lat, ul_lon, lr_lat, lr_lon]))

# Define output type of url call
output = 'json'

## Join elements of GediFinder URL

# Join together components of url
urlList = [
       f'product={productLevel1B}',
       f'version={version}',
       f'bbox={bbox}',
       f'output={output}'
]

url = lpdaac + "?" + '&'.join(urlList)

## Get list of granules

# Making a GET request
response = requests.get(url)

# Verify a successful request call
if response:
  print('Success!')
  granulesList = response.json()['data'] # Pull data from response
else:
  print('An error has occurred.')

# Strip extra information away from granule file names
stripped_granulesList = [s[-49:] for s in granulesList]

# Join list of granules and print list to copy and paste into Earthdata Search
# Use copy icon at end of output to quickly copy all granule names
','.join(stripped_granulesList)
