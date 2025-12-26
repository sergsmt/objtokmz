#!/usr/bin/env python3
"""
Convert OBJ file to KMZ with georeferencing
"""
import os
import pyassimp
import simplekml
import shutil
import tempfile
import pyproj
from pyproj import CRS, Transformer
import re
import fire
from collada import Collada
import logging

logger = logging.getLogger(__name__)

# Enable network access for pyproj to fetch grid files if needed
pyproj.network.set_network_enabled(True)

# WGS84 UTM 35N
GEOREF_LINE1 = re.compile(r"^WGS84 UTM (\d+)(N|S)$")
# easting northing
GEOREF_LINE2 = re.compile(r"^(\d+)\s+(\d+)$")


def read_georef(georef_path: str) -> tuple[float, float, float]:
    """
    Read georeference from a file and return latitude and longitude

    The georef file is expected to have the following format:
    WGS84 UTM <zone><N|S>
    <easting> <northing>

    Args:
        georef_path (str): Path to the georeference file

    Returns:
        tuple[float, float, float]: Longitude, Latitude, and Altitude

    """

    with open(georef_path, "r") as f:
        line1 = f.readline(99).strip()
        line2 = f.readline(99).strip()

    match1 = GEOREF_LINE1.match(line1)
    match2 = GEOREF_LINE2.match(line2)

    if not match1 or not match2:
        raise ValueError("Invalid georeference file format")

    zone = int(match1.group(1))
    hemisphere = match1.group(2)
    easting = int(match2.group(1))
    northing = int(match2.group(2))

    south = hemisphere == "S"

    crs = CRS.from_dict({"proj": "utm", "zone": zone, "south": south})

    # Horizontal transformer from UTM to WGS84
    h_transformer = Transformer.from_crs(crs, CRS.from_epsg("4326"), always_xy=True)
    lon, lat = h_transformer.transform(easting, northing)

    # Vertical transformer from WGS84 ellipsoidal to WGS84 + EGM96
    v_transformer = Transformer.from_crs(
        "EPSG:4979",  # WGS84 ellipsoidal
        "EPSG:4326+5773",  # WGS84 + EGM96
        always_xy=True,
    )
    lon, lat, alt = v_transformer.transform(lon, lat, 0.0)

    return lon, lat, alt


def obj_to_dae(obj_path: str, dae_path: str):
    """
    Convert OBJ file to DAE format
    Images referenced in the OBJ/MTL files are copied to the DAE directory.

    Args:
        obj_path (str): Path to the input OBJ file
        dae_path (str): Path to the output DAE file

    Returns:
        None
    """

    # Convert OBJ to DAE
    # mtl will be handled by pyassimp automatically
    with pyassimp.load(obj_path) as scene:
        pyassimp.export(scene, dae_path, file_type="collada")

    obj_dir = os.path.dirname(obj_path)
    dae_dir = os.path.dirname(dae_path)

    # copy images referenced in the DAE
    mesh = Collada(dae_path)
    for image in mesh.images:
        # assume that image path is relative to the OBJ directory
        img_source = os.path.join(obj_dir, image.path)
        img_dest = os.path.join(dae_dir, os.path.basename(image.path))
        if os.path.exists(img_source):
            shutil.copy(img_source, img_dest)
        else:
            logger.warning(f"Image file {img_source} not found.")


def dae_to_kml(dae_path: str, lat: float, lon: float, alt: float, kml_dir: str):
    """
    Create a KML file referencing the DAE model with georeferencing

    Args:
        dae_path (str): Path to the input DAE file
        lat (float): Latitude for georeferencing
        lon (float): Longitude for georeferencing
        kml_dir (str): Directory to save the KML and associated files

    Returns:
        None
    """

    dae_name = os.path.basename(dae_path)

    kml = simplekml.Kml()
    model = kml.newmodel(name="The Model")
    model.link.href = dae_name
    model.location.latitude = lat
    model.location.longitude = lon
    model.location.altitude = alt  # - 320
    model.altitudemode = simplekml.AltitudeMode.absolute
    model.orientation.heading = 180
    model.orientation.tilt = 270
    model.orientation.roll = 0
    model.scale.x = 1
    model.scale.y = 1
    model.scale.z = 1
    kml.save(os.path.join(kml_dir, "model.kml"))


def obj_to_kmz(obj_path: str, georef_path: str, kmz_path: str):
    """Convert OBJ file to KMZ with georeferencing

    Args:
        obj_path (str): Path to the input OBJ file
        georef_path (str): Path to the georeference file
        kmz_path (str): Path to the output KMZ file
    """

    # Read georeference
    lon, lat, alt = read_georef(georef_path)

    with tempfile.TemporaryDirectory() as tempdir:

        dae_path = os.path.join(tempdir, "model.dae")

        # Convert OBJ to DAE and save in tempdir
        obj_to_dae(obj_path, dae_path)

        # Create KML in tempdir
        dae_to_kml(dae_path, lat, lon, alt, tempdir)

        # Create KMZ (zip) archive
        shutil.make_archive(kmz_path.replace(".kmz", ""), "zip", tempdir)
        shutil.move(kmz_path.replace(".kmz", "") + ".zip", kmz_path)


if __name__ == "__main__":
    # Command line interface
    fire.Fire(obj_to_kmz)
