# ***************************************
# ***Overview***
# Script name: Solar_Power.py
# Purpose: Process DSM raster and compute solar power potential for every rooftop in a neighborhood
# Project: Solar power potential in a neighborhood tutorial
# Extent: Glover park neighborhood in DC
# Last updated: June 22, 2019
# Author: Delphine Khanna
# Organization: Esri
# Note: This Arcpy script is meant to run in ArcGIS Desktop. It is NOT optimized for complete unsupervised automation.
# ***************************************


# Import Arcpy modules:
import arcpy
import arcpy.sa # Spatial Analyst

# *********
# Set up global variables
#base_path = "C:\\Users\\del10314\\Desktop\\Dk_projects\\Solar_power2"
base_path = "C:\\Users\\delph\\Desktop\\GIS\\Esri_internship\\Solar_power2"
main_data_path = base_path + "\\Solar_power.gdb"
util_data_path = base_path + "\\Solar_power_util.gdb"

# *****************************************
# Functions

# Print the current action and time
def print_time_stamp(action):
    current_DT = datetime.datetime.now()
    print(action + " Processing -- "
          + current_DT.strftime("%Y-%b-%d %I:%M:%S %p"))

# Set up the ArcGIS environment variables
def set_up_env():
    arcpy.env.workspace = main_data_path
    arcpy.env.overwriteOutput = True
    current_extent = "DSM"
    arcpy.env.extent = current_extent
    arcpy.env.outputCoordinateSystem = current_extent
    arcpy.env.mask = current_extent
    arcpy.env.snapraster = current_extent
    arcpy.env.cellSize = current_extent

# Prepare the Digital Surface Model raster
def prep_DSM():
    # Clip the DSM raster to the shape of the neighborhood
    #Note - Rectangle: Left Bottom Right Top
    arcpy.Clip_management(util_data_path + "\\DSM_non_clipped",
            "392863.254500002 138765.860800002 394195.720000002 139840.051600002",
            main_data_path + "\\DSM",
            util_data_path + "\\Neighborhood_Boundaries_Buffered",
            "-3.402823e+38", "ClippingGeometry")

    # Create hillshade (Note: it is better to create as a simple layer instead)
    outHillshade = arcpy.sa.Hillshade("DSM")
    outHillshade.save(main_data_path + "\\DSM_hillshade1")
    arcpy.MakeRasterLayer_management(main_data_path + "\\DSM_hillshade1", "DSM_hillshade")

# Generate the solar radiation rasters for 4 different days
def generate_SR_raster_for_1_day(day_in_year, SR_ras_name):
    # Note: AreaSolarRadiation (in_surface_raster, {latitude}, {sky_size}, {time_configuration},
    # {day_interval}, {hour_interval}, {each_interval}, {z_factor}, {slope_aspect_input_type},
    # {calculation_directions}, {zenith_divisions}, {azimuth_divisions}, {diffuse_model_type},
    # {diffuse_proportion}, {transmittivity})
    # Note: day_interval=14 is just a default here, and not used actively
    outSolarRadiation = arcpy.sa.AreaSolarRadiation ("DSM", 38.919343379181, 200, WithinDay(day_in_year, 0, 24),
                        14, 1, "NOINTERVAL", 1, "FROM_DEM", 16, 8, 8, "UNIFORM_SKY",
                        0.3, 0.5)
    outSolarRadiation.save(main_data_path + "\\" + SR_ras_name)

def generate_all_SR_rasters():
    generate_SR_raster_for_1_day(80, "SR_Mar20")
    generate_SR_raster_for_1_day(172, "SR_Jun21")
    generate_SR_raster_for_1_day(266, "SR_Sep23")
    generate_SR_raster_for_1_day(356, "SR_Dec22")

    # Create SR average raster
    # Note: when doing it manually, use tool Raster Calculator with expression:
    #        ("SR_Mar20" + "SR_Jun21"+ "SR_Sep23" + "SR_Dec22")/4
    outSR_avg = (arcpy.sa.Raster("SR_Mar20") + arcpy.sa.Raster("SR_Jun21") +
                arcpy.sa.Raster("SR_Sep23") + arcpy.sa.Raster("SR_Dec22"))/4
    outSR_avg.save(main_data_path + "\\SR_avg")
    arcpy.MakeRasterLayer_management(main_data_path + "\\SR_avg", "SR_avg")

# Select only the buildings whose footprint is large enough
def find_large_buildings():
    # Select the rooftops that are large enough to be suitable:
    arcpy.SelectLayerByAttribute_management("Building_Footprints_Clipped", "NEW_SELECTION", "Shape_Area >= 40")
    # Save to a new feature class and do some clean up
    arcpy.CopyFeatures_management("Building_Footprints_Clipped", main_data_path + "\\Building_Footprints_Large")
    arcpy.SelectLayerByAttribute_management("Building_Footprints_Clipped", "CLEAR_SELECTION")

# Generate a raster showing the average solar radiation only for the building footprints
def get_SR_for_buildings():
    outExtractByMask = arcpy.sa.ExtractByMask("Avg_Solar_Radiation_Shifted", "Building_Footprints_Large")
    outExtractByMask.save("Avg_SR_for_buildings")
    # Load the raster into the MXD
    arcpy.MakeRasterLayer_management(main_data_path + "\\Avg_SR_for_buildings", "Avg_SR_for_buildings")


# Remove the areas where the slope is too high to be suitable for solar panels
def remove_low_slope():
    outSlope = arcpy.sa.Slope("DSM_50cm_clipped_shifted", "DEGREE")
    outSlope.save(main_data_path + "\\Slope_clipped_shifted")
    arcpy.MakeRasterLayer_management(main_data_path + "\\Slope_clipped_shifted", "Slope_clipped_shifted")

    outCon = arcpy.sa.Con ("Slope_clipped_shifted", "Avg_SR_for_buildings", "", "VALUE <= 45")
    outCon.save("Avg_SR_for_buildings_low_slope")
    arcpy.MakeRasterLayer_management(main_data_path + "\\Avg_SR_for_buildings_low_slope", "Avg_SR_for_buildings_low_slope")

# Remove areas where the average solar radiation amounts are too low
def remove_low_performance_areas():
    outCon = arcpy.sa.Con ("Avg_SR_for_buildings_low_slope", "Avg_SR_for_buildings_low_slope", "", "VALUE >= 2200")
    outCon.save("Avg_SR_for_buildings_high_performance")
    arcpy.MakeRasterLayer_management(main_data_path + "\\Avg_SR_for_buildings_high_performance", "Avg_SR_for_buildings_high_performance")


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
                                        main_data_path + "\\" + out + "_table", "DATA", "MEAN")
        arcpy.AddJoin_management(zone, "OBJECTID", out + "_table", "OBJECTID_1", "KEEP_ALL")
        arcpy.CopyFeatures_management(zone, main_data_path + "\\" + out)
        arcpy.RemoveJoin_management(zone)

# Remove buildings that have too little surface that is suitable for solar panels
def remove_low_suitability_bldgs():
    # Select the rooftops that have enough suitability are for solar panels:
    arcpy.SelectLayerByAttribute_management("Bldg_with_stats", "NEW_SELECTION", "Bldg_with_stats_table_AREA >= 30")
    # Save to a new feature class and do some clean up
    arcpy.CopyFeatures_management("Bldg_with_stats", main_data_path + "\\Suitable_buildings")
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
prep_DSM()
generate_all_SR_rasters()
find_suitable_areas()
stats_per_building()
stats_per_neighborhood()
print_time_stamp("Done")
