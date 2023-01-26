"""
This file contains various helper and worker functions for the plug-in, such as working with coordinates
creating point layer and checking input data validity.
"""
import json
from os import getcwd, path

from pandas import DataFrame, to_numeric
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsCoordinateTransformContext, QgsProject, \
    QgsFeature, QgsVectorLayer, QgsGeometry, QgsPointXY
from qgis.utils import iface, QgsMessageLog
from requests import get

"""
Retrieve a location of the qgis plugin folder to store config.json file to global variable. Expression is from
https://stackoverflow.com/questions/4060221/
"""
script_location = path.realpath(path.join(getcwd(), path.dirname(__file__)))


def transform_bb_coords(current_crs, extent):
    """
    transforms bounding box coordinates to lon/lat in decimal degrees
    in case current coordinate system is in meters
    """
    dest_crs = QgsCoordinateReferenceSystem.fromEpsgId(4326)
    transform = QgsCoordinateTransform(current_crs, dest_crs, QgsCoordinateTransformContext())
    transformed_extent = transform.transformBoundingBox(extent)
    return transformed_extent


def get_current_map_extent():
    """ gets current QGIS map extent """
    extent = iface.mapCanvas().extent()
    current_crs = iface.mapCanvas().mapSettings().destinationCrs()
    new_box = transform_bb_coords(current_crs, extent)
    return new_box.xMinimum(), new_box.xMaximum(), new_box.yMaximum(), new_box.yMinimum()


def get_layer_extent_by_index(layer_index):
    """ this function gets extent of the layer by it's index """
    layers = list(QgsProject.instance().mapLayers().values())
    layer_extent = layers[layer_index].extent()
    return layer_extent.xMinimum(), layer_extent.xMaximum(), layer_extent.yMaximum(), layer_extent.yMinimum()


def write_settings(settings):
    """
    writes settings in the settings dialog in a json format. script_location variable is defined
    at the top of the module.
    """
    with open(path.join(script_location, 'settings.json'), 'w') as f:
        json.dump(settings, f)


def read_settings():
    """ reads settings from the json file into Python objects """
    with open(path.join(script_location, 'settings.json'), 'r') as f:
        return json.load(f)


def check_api_key(api_key):
    """
    this function checks validity of the Purpleair API key using their web api as explained here:
    https://api.purpleair.com/#api-keys-check-api-key
    if the key is invalid(blocked) or malformed, the api route returns 403 status code, if key is valid - 201
    """
    try:
        response = get("https://api.purpleair.com/v1/keys", headers={"X-API-Key": api_key})
        if response.status_code == 201:
            return True
        else:
            return False
    except:
        return False


def validate_input_coordinates(xmin, xmax, ymin, ymax):
    """
    this function provides basic validation of the manually input coordinates in the main dialog
    the idea is that coordinates must be able to convert to float, must be within the appropriate ranges and
    one coordinate must be larger than another
    """
    try:
        xmin = float(xmin)
        xmax = float(xmax)
        ymin = float(ymin)
        ymax = float(ymax)
        xmin_range = -180 <= xmin <= 180
        xmax_range = -180 <= xmax <= 180
        ymin_range = -90 <= ymin <= 90
        ymax_range = -90 <= ymax <= 90
        x_max = xmax > xmin
        y_max = ymax < ymin
        if all((xmin_range, xmax_range, ymin_range, ymax_range, x_max, y_max)):
            return True
        return False
    except:
        return False


def layer_from_df(dataframe, layer_name='pa_sensors'):
    """
    this function creates a QGis point vector layer from the input pandas dataframe. The approach is
    very similar to what we did in GEOG489 class. It requires a dataframe with long, lat columns.
    All columns should contain numeric data, since all the resulting columns are hard-coded to have
    double type.
    """
    # creating layer description from the list of columns of the pandas dataframe
    layer_descr = "Point?crs=EPSG:4326" + "".join([f"&field={column}:double" for column in dataframe.columns])
    # creating new empty  in-memory layer
    layer = QgsVectorLayer(layer_descr, layer_name, 'memory')
    prov = layer.dataProvider()
    pa_sensor_list = []
    # iterating through the rows in the Pandas dataframe and creating QGis features
    for index, row in dataframe.iterrows():
        pa_sensor = QgsFeature()
        pa_sensor.setAttributes(list(row))
        pa_sensor.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(row['lon'], row['lat'])))
        pa_sensor_list.append(pa_sensor)
    prov.addFeatures(pa_sensor_list)
    return layer
