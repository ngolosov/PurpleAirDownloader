"""
This file contains main business logic for the plug-in, such as Thread class to run the workers,
worker function to download the data from Thingspeak cloud and calculate_average function to calculate
average values for the pollutant concentrations for the reporting period
"""
import concurrent.futures

from PyQt5.QtCore import QThread, pyqtSignal
from pandas import DataFrame, concat, to_numeric
from qgis.core import QgsProject
from qgis.utils import QgsMessageLog
from requests import get


from .pa_downloader_heplers import read_settings, layer_from_df


class Thread(QThread):
    # initializing QT signal that communicate progress from the child thread to the main thread
    signal = pyqtSignal(int)

    def __init__(self, jobs):
        super(QThread, self).__init__()
        # this instance variable contains input parameters that used in the run method
        self.jobs = jobs
        self.stop_download = False

    def run(self):
        """
        this method actually does all the heavy lifting:
        runs the worker threads to retrieve data for individual sensors from the Thingspeak cloud
        and communicate progress using signal.emit()
        """
        # use threads instead of processes, since the code is being run in the Python embedded into qgis
        # when I run multiprocessing, it starts multiple instances of QGIS(one per process)
        # threads provide multitasking and run in the single process
        with concurrent.futures.ThreadPoolExecutor(4) as executor:
            queue = [executor.submit(worker, job) for job in self.jobs]
            # this loop is needed to monitor the completed tasks in the queue
            # as_completed() method immediately yields completed(or canceled) future as soon it completes
            # and the loop moves one step forward
            for step, _ in enumerate(concurrent.futures.as_completed(queue), 1):
                progress = int(step / len(self.jobs) * 100)
                self.signal.emit(progress)
                # if user click Stop download button
                if self.stop_download:
                    # we need to cancel every pending future one by one
                    for future in queue:
                        future.cancel()
                    # this one frees memory, but does not cancel pending futures.
                    # moreover, there's no way to kill running futures :(
                    executor.shutdown(wait=False)
                    # emit 100% completion and break the loop
                    self.signal.emit(100)
                    break

        # if the user did not cancel the download, process the resulting data
        if not self.stop_download:
            # retrieving the results from the individual futures
            results = [future.result() for future in queue]
            # calculating averages using the helper function
            averages = [calculate_average(frame) for frame in results if type(calculate_average(frame)) == DataFrame]
            # concatenating Pandas dataframes
            averages = concat(averages)
            # creating point layer from Pandas dataframe
            point_layer = layer_from_df(averages)
            # adding point layer to QGis. Normally addMapLayer alone should do the job
            QgsProject.instance().addMapLayer(point_layer)
            # although that did not add the layer to the list of the layers, when run from the plugin code
            # on QGis version 3.16.11. The line below fixed that, although I not sure about other QGis versions
            # maybe it will add the layer twice to the list(???)
            QgsProject.instance().layerTreeRoot().addLayer(point_layer)


def worker(job):
    """
    this function download data for individual sensors from Thingspeak cloud. The function runs in
    multiple threads using concurrent.futures
    """
    # unpacking job parameters
    primary_key_a, primary_id_a, latitude, longitude, start, end, average = job
    # creating list of the get query parameters to request date from Thingspeak channel
    ts_payload = {"api_key": primary_key_a,
                  "start": start,
                  "end": end,
                  "average": average
                  }

    # trying to download the data and return the result. timeout parameter is important, otherwise in case of network
    # issues it could hang indefinitely
    try:
        thingspeak_content = get(f"https://api.thingspeak.com/channels/{primary_id_a}/feed.json", ts_payload, timeout=60)
        return latitude, longitude, thingspeak_content.json()
    except Exception as e:
        QgsMessageLog.logMessage(f"error during processing channel with ID: {primary_id_a}, key: {primary_key_a}, "
                                 f"exception: {str(e)}",
                                 'PurpleAir Downloader')
        return {}


def get_sensor_list(input_params):
    """
    Function to retrieve list of the sensors from the Purpleair API
    It's pretty fast so I decided to run it from the GUI code, instead of separate thread.
    If it run from the main GUI
    The  retrieves the sensors and creates list of jobs

    """
    # read settings, such as api key and number of threads, they're used below
    settings = read_settings()
    # populating input parameters for the purpleair API query using requests
    start = input_params['start_date']
    end = input_params['end_date']
    average = "daily"
    fields = ["primary_key_a", "primary_id_a", "latitude", "longitude"]

    pa_query_params = {"location_type": input_params['sensor_type'],
                       "api_key": settings['api_key'],
                       "nwlng": input_params['extent'][0],
                       "selng": input_params['extent'][1],
                       "nwlat": input_params['extent'][2],
                       "selat": input_params['extent'][3]
                       }

    # getting list of the sensors from Purpleair API
    content = get("https://api.purpleair.com/v1/sensors", {"fields": ",".join(fields), **pa_query_params})
    purpleair_data = content.json()
    # Purpleair API documentation suggests that order of fields is not stable in the response,
    # so here I take care of it by retrieving filed indexes by names and matching data with indexes
    field_indexes = [purpleair_data['fields'].index(field) for field in fields]
    # creating list of jobs, similarly what we've used for multiprocessing
    jobs = [[data_item[index] for index in field_indexes] + [start, end, average] for data_item in
            purpleair_data['data']]

    return jobs

def calculate_average(result):
    """
    this function converts downloaded JSON data to the Pandas dataframes, calculates average value for each column
    in the input dataframe and return one-row dataframe with average values of atmospheric pollution metrics
    """
    try:
        # unpack input tuple
        lat, lon, ts_content = result
        # getting list of the column names from json to use for the new dataframes
        column_names = [value for key, value in ts_content['channel'].items() if key.startswith("field")]
        # creating dataframes with default column names
        df = DataFrame(ts_content['feeds'])
        df = df.drop(["created_at"], axis=1)
        # applying names of the columns from the list
        df.columns = column_names
        # removing NaN values and converting to numbers
        df = df.apply(to_numeric)
        df = df.dropna()
        # if dataframe contains more that  0 rows, calculating mean values on subset of columns.
        if len(df.index) > 0:
            column_subset = [
                'PM1.0 (ATM)',
                'PM2.5 (ATM)',
                'PM10.0 (ATM)',
                'PM2.5 (CF=1)']
            # transposing the dataframe
            mean_values = DataFrame(df[column_subset].mean()).T
            # adding columns such as count - numbers of days used for calculating mean, lon and lat values
            mean_values["count"], mean_values["lon"], mean_values["lat"] = len(df.index), lon, lat
            return mean_values
    except Exception as e:
        pass
