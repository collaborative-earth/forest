# --------------------------------------- LIBRARIES --------------------------------------------- #
# Needed libraries for data clipping
library(rGEDI)
library(sf)
library(data.table)

# Libraries for data download
library(sys)
library(getPass)
library(httr)
# ----------------------------------- SET UP ENVIRONMENT ---------------------------------------- #
# Set directory for downloading files
download.dir <- '/Users/ryancarlson/Earthshot_Labs/Carbon/GEDI/Data/Download'

# Set directory for clipped data files
clipped.dir <- '/Users/ryancarlson/Earthshot_Labs/Carbon/GEDI/Data/Clipped'
# Set up .netrc file
usr <- file.path(Sys.getenv("USERPROFILE"))                  # Retrieve home dir (for netrc file)
if (usr == "") {usr = Sys.getenv("HOME")}                    # If no user profile exists, use home
netrc <- file.path(usr,'.netrc', fsep = .Platform$file.sep)  # Path to netrc file
# ----------------------------------- CREATE .NETRC FILE ----------------------------------------- #
# If you already have a .netrc file with your Earthdata Login credentials stored in your home
# directory, this portion will be skipped. Otherwise you will be prompted for your NASA Earthdata
# Login Username/Password and a netrc file will be created to store your credentials (in home dir)
if (file.exists(netrc) == FALSE || grepl("urs.earthdata.nasa.gov",
                                         readLines(netrc)) == FALSE) {
  netrc_conn <- file(netrc)
  # User will be prompted for NASA Earthdata Login Username and Password below
  writeLines(c("machine urs.earthdata.nasa.gov",
               sprintf("login %s", getPass(msg = "Enter NASA Earthdata Login Username \n (or create an account at urs.earthdata.nasa.gov) :")),
               sprintf("password %s", getPass(msg = "Enter NASA Earthdata Login Password:"))), netrc_conn)
  close(netrc_conn)
}
# ---------------------------------- SET CLIPPED VARIABLES --------------------------------------- #
# Define a bounding box
ul_lat <- -13.75831
lr_lat <- -13.71244
ul_lon <- -44.10066
lr_lon <- -44.15036
# Make bbox spatial and expand bbox by a tad
bbox.sf <- sf::st_bbox(
  c(xmin = lr_lon, xmax = ul_lon, ymax = lr_lat, ymin = ul_lat),
  crs = st_crs(4326)
) %>%
  st_as_sfc %>%
  st_as_sf
# Set date range
daterange = c("2019-05-01","2020-12-31")
# ------------------------------------- FIND GEDI FILES ------------------------------------------ #
# Currently based on index, might want to change to by name
gLevel1B <- rGEDI::gedifinder(
  product = "GEDI01_B", ul_lat, ul_lon,
  lr_lat, lr_lon, version = "001", daterange = daterange
)
gLevel2A <- rGEDI::gedifinder(
  product = "GEDI02_A", ul_lat, ul_lon,
  lr_lat, lr_lon, version = "001", daterange = daterange
)
gLevel2B <- rGEDI::gedifinder(
  product = "GEDI02_B", ul_lat, ul_lon,
  lr_lat, lr_lon, version = "001", daterange = daterange
)
gedi.list <- 1:length(gLevel1B) %>% lapply(function(x){list(gLevel1B[x],
                                                            gLevel2A[x],
                                                            gLevel2B[x])})
# ---------------------------CONNECT TO DATA POOL AND DOWNLOAD FILES------------------------------ #
## WARNING! Do not run unless you want to download data!
gedi.list %>% lapply(function(z){
  # Uncomment the line below to download data
  z %>% lapply(function(x){gediDownload(x, outdir = download.dir)})
  # Creates lists of file paths and filenames of downloaded data
  data.list <- list.files(path = download.dir, full.names = TRUE)
  names(data.list) <- list.files(path = download.dir, full.names = FALSE) %>% substr(0,8)
  fileNames.list <- list.files(path = download.dir, full.names = FALSE)
  names(fileNames.list) <- list.files(path = download.dir, full.names = FALSE) %>% substr(0,8)
  # Read in Data
  gedilevel1b <- rGEDI::readLevel1B(level1Bpath = file.path(data.list['GEDI01_B']))
  gedilevel2a <- rGEDI::readLevel2A(level2Apath = file.path(data.list['GEDI02_A']))
  gedilevel2b <- rGEDI::readLevel2B(level2Bpath = file.path(data.list['GEDI01_B']))
  # Expand the bbox just a touch
  expanded.bbox <- (bbox.sf %>% sf::st_buffer(0.1) %>% sf::st_bbox())
  # Crop the results
  rGEDI::clipLevel1B(
    gedilevel1b,
    expanded.bbox$xmin,
    expanded.bbox$xmax,
    expanded.bbox$ymin,
    expanded.bbox$ymax,
    output=file.path(clipped.dir, fileNames.list['GEDI01_B'])
  )
  rGEDI::clipLevel2A(
    gedilevel2a,
    expanded.bbox$xmin,
    expanded.bbox$xmax,
    expanded.bbox$ymin,
    expanded.bbox$ymax,
    output=file.path(clipped.dir, fileNames.list['GEDI02_A'])
  )
  rGEDI::clipLevel2B(
    gedilevel2b,
    expanded.bbox$xmin,
    expanded.bbox$xmax,
    expanded.bbox$ymin,
    expanded.bbox$ymax,
    output=file.path(clipped.dir, fileNames.list['GEDI02_B'])
  )
  # Close files before deleting?? Not sure if this needs to be donw
  close(gedilevel1b)
  close(gedilevel2a)
  close(gedilevel2b)
  # Delete files in download directory
  unlink(paste0(download.dir,"/*"))
})
