# QGIS PurpleAir Downloader Plugin

This QGIS plugin provides an easy-to-use interface for downloading PurpleAir air quality sensor data within a specified bounding box or using the current map extent. The plugin utilizes the PurpleAir API and supports downloading data based on the current map view, a specific layer extent, or manually entered coordinates.

## Features

- Retrieve data for outdoor and indoor sensors
- Download data based on the current map view, a specific layer extent, or manually entered coordinates
- Validate user input for bounding box coordinates
- Concurrent downloading of sensor data to improve performance
- Progress bar to track the download process
- Settings dialog to manage PurpleAir API key and the number of concurrent downloads

## Installation

1. Download the plugin repository as a zip file.
2. Open QGIS and go to `Plugins` > `Manage and Install Plugins...`
3. Click on the `Install from ZIP` tab and browse to the downloaded zip file.
4. Click on `Install Plugin` to install the PurpleAir Downloader plugin.

## Usage

After installation, you can access the plugin from the QGIS toolbar or by going to `Plugins` > `PurpleAir Downloader` > `Download PurpleAir Data`.

1. Choose the extent for downloading sensor data:
   - Use the current map extent
   - Specify bounding box coordinates manually
   - Use the extent of a specific layer

2. Set the start and end dates for the data you want to download.

3. Choose the sensor type (outdoor or indoor).

4. Click on the `Download` button to start downloading sensor data. The progress bar will indicate the progress of the download process.

5. Click on the `Settings` button to open the settings dialog, where you can manage the PurpleAir API key and the number of concurrent downloads.

## Dependencies

This plugin requires QGIS 3.x and PyQt5. The required Python packages are:

- PyQt5
- qgis.core
- qgis.utils

These packages should be available in your QGIS Python environment.

## License

This project is licensed under the MIT License.
