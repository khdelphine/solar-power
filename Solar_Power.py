# ***************************************
# ***Overview***
# Script name: Solar_Power.py
# Purpose: Process DSM raster and compute solar power potential for every rooftop in a neighborhood
# Project: Solar power potential in a neighborhood tutorial
# Extent: Glover park neighborhood in DC
# Last updated: June 19, 2019
# Author: Delphine Khanna
# Organization: Esri
# Note: This Arcpy script is meant to run in ArcGIS Desktop. It is NOT optimized for complete unsupervised automation.
# ***************************************


# Import Arcpy modules:
import arcpy
import arcpy.sa # Spatial Analyst


# *********
# Set up global variables
base_path = "C:\\Users\\del10314\\Desktop\\Dk_projects\\Solar_power2"
tiff_home = base_path + "\\New_data2"
fc_home = base_path + "\\Solar_power2.gdb"


# *****************************************
# Functions

# Print the current action and time
def print_time_stamp(action):
    current_DT = datetime.datetime.now()
    print(action + " Processing -- "
          + current_DT.strftime("%Y-%b-%d %I:%M:%S %p"))

# Set up the ArcGIS environment variables
def set_up_env():
    arcpy.env.workspace = tiff_home
    arcpy.env.overwriteOutput = True
    current_extent = "GloverParkBoundaries_Buffered"
    arcpy.env.extent = current_extent
    arcpy.env.outputCoordinateSystem = current_extent
    arcpy.env.mask = current_extent


# Select only the buildings whose footprint is large enough
def find_large_buildings():
    # Select the rooftops that are large enough to be suitable:
    arcpy.SelectLayerByAttribute_management("Building_Footprints_Clipped", "NEW_SELECTION", "Shape_Area >= 40")
    # Save to a new feature class and do some clean up
    arcpy.CopyFeatures_management("Building_Footprints_Clipped", fc_home + "\\Building_Footprints_Large")
    arcpy.SelectLayerByAttribute_management("Building_Footprints_Clipped", "CLEAR_SELECTION")

# Generate a raster showing the average solar radiation only for the building footprints
def get_SR_for_buildings():
    outExtractByMask = arcpy.sa.ExtractByMask("Avg_Solar_Radiation_Shifted.tif", "Building_Footprints_Large")
    outExtractByMask.save("Avg_SR_for_buildings.tif")
    # Load theraster into the MXD
    arcpy.MakeRasterLayer_management(tiff_home + "\\Avg_SR_for_buildings.tif", "Avg_SR_for_buildings")


# Remove the areas where the slope is too high to be suitable for solar panels
def remove_low_slope():
    outSlope = arcpy.sa.Slope("DSM_50cm_clipped_shifted.tif", "DEGREE")
    outSlope.save(tiff_home + "\\Slope_clipped_shifted.tif")
    arcpy.MakeRasterLayer_management(tiff_home + "\\Slope_clipped_shifted.tif", "Slope_clipped_shifted")

    outCon = arcpy.sa.Con ("Slope_clipped_shifted", "Avg_SR_for_buildings", "", "VALUE <= 45")
    outCon.save("Avg_SR_for_buildings_low_slope.tif")
    arcpy.MakeRasterLayer_management(tiff_home + "\\Avg_SR_for_buildings_low_slope.tif", "Avg_SR_for_buildings_low_slope")

# Remove areas where the average solar radiation amounts are too low
def remove_low_performance_areas():
    outCon = arcpy.sa.Con ("Avg_SR_for_buildings_low_slope", "Avg_SR_for_buildings_low_slope", "", "VALUE >= 2200")
    outCon.save("Avg_SR_for_buildings_high_performance.tif")
    arcpy.MakeRasterLayer_management(tiff_home + "\\Avg_SR_for_buildings_high_performance.tif", "Avg_SR_for_buildings_high_performance")


# Find the areas suitable for solar power production
def find_suitable_areas():
    find_large_buildings()
    get_SR_for_buildings()
    remove_low_slope()
    remove_low_performance_areas()

# Compute the Solar Radiation amount for each "zone"
def get_stats_per_zone(zone, out):
        # Compute SR stats for each zone. The output is a table
        arcpy.sa.ZonalStatisticsAsTable(zone, "OBJECTID", "Avg_SR_for_buildings_high_performance",
                                        fc_home + "\\" + out + "_table", "DATA", "MEAN")
        arcpy.AddJoin_management(zone, "OBJECTID", out + "_table", "OBJECTID_1", "KEEP_ALL")
        arcpy.CopyFeatures_management(zone, fc_home + "\\" + out)
        arcpy.RemoveJoin_management(zone)

# Remove buildings that have too little surface that is suitable for solar panels
def remove_low_suitability_bldgs():
    # Select the rooftops that have enough suitability are for solar panels:
    arcpy.SelectLayerByAttribute_management("Bldg_with_stats", "NEW_SELECTION", "Bldg_with_stats_table_AREA >= 30")
    # Save to a new feature class and do some clean up
    arcpy.CopyFeatures_management("Bldg_with_stats", fc_home + "\\Suitable_buildings")
    arcpy.SelectLayerByAttribute_management("Bldg_with_stats", "CLEAR_SELECTION")

# Compute the potential electric power production
def compute_EP_numbers(zone, prefix):
    # Per "zone":
    arcpy.AddField_management(zone, "Daily_EP_Wh_per_sqm","DOUBLE")
    formula_expr = "(!" + prefix + "_with_stats_table_MEAN! * 0.15) * 0.86"
    arcpy.CalculateField_management(zone, "Daily_EP_Wh_per_sqm", formula_expr)

    # Per "zone" per sq m
    arcpy.AddField_management(zone, "Daily_EP_kWh_total","DOUBLE")
    formula_expr2 = "(!Daily_EP_Wh_per_sqm! * !" + prefix + "_with_stats_table_AREA!)/ 1000"
    arcpy.CalculateField_management(zone, "Daily_EP_kWh_total", formula_expr2)


def stats_per_building():
    get_stats_per_zone("Building_Footprints_Large", "Bldg_with_stats")
    remove_low_suitability_bldgs()
    compute_EP_numbers("Suitable_buildings", "Bldg")

def stats_per_neighborhood():
    get_stats_per_zone("GloverParkBoundaries", "Neighborhood_with_stats")
    compute_EP_numbers("Neighborhood_with_stats", "Neighborhood")



# ***************************************
# Begin Main
print_time_stamp("Start")
set_up_env()
compute_SR_for_a_day()
#find_suitable_areas()
#stats_per_building()
#stats_per_neighborhood()
print_time_stamp("Done")
