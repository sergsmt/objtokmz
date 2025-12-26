import os
import tempfile
import bs4
import pytest
from objtokmz import read_georef, obj_to_dae, dae_to_kml


def test_read_georef():
    georef_content = "WGS84 UTM 35N\n418574 5345544\n"

    with tempfile.NamedTemporaryFile() as tmpfile:
        tmpfile.write(georef_content.encode('utf-8'))
        tmpfile_path = tmpfile.name
        tmpfile.flush()

        lon, lat, alt = read_georef(tmpfile_path)
        assert abs(lon - 25.9) < 0.1
        assert abs(lat - 48.25) < 0.1
        assert abs(alt + 33.58) < 0.1


def test_read_georef_invalid():
    georef_content = "INVALID DATA\n"

    with tempfile.NamedTemporaryFile() as tmpfile:
        tmpfile.write(georef_content.encode('utf-8'))
        tmpfile_path = tmpfile.name
        tmpfile.flush()

        with pytest.raises(Exception, match="Invalid georeference file format"):
            read_georef(tmpfile_path)


def test_obj_to_dae():
    # Create a temporary OBJ file with a simple cube

    mtl_content = ""
    png_files = [
        "texture1.png",
        "texture2.png"
    ]

    for i, png_file in enumerate(png_files):
        mtl_content += f"""
newmtl material{i+1}
Ka 1.000 1.000 1.000
Kd 1.000 1.000 1.000
Ks 0.000 0.000 0.000
d 1.0
Ns 0.000
illum 2
map_Kd texture{i+1}.png\n
"""

    obj_content = """# Simple cube
mtllib cube.mtl
o Cube
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
v 0 0 1
v 1 0 1
v 1 1 1
v 0 1 1
f 1 2 3 4
f 5 6 7 8
f 1 5 8 4
f 2 6 7 3
f 4 3 7 8
f 1 2 6 5
"""

    with tempfile.TemporaryDirectory() as srcdir, \
         tempfile.TemporaryDirectory() as dstdir:

        obj_path = os.path.join(srcdir, "cube.obj")
        mtl_path = os.path.join(srcdir, "cube.mtl")
        dae_path = os.path.join(dstdir, "cube.dae")

        with open(obj_path, 'w') as f:
            f.write(obj_content)

        with open(mtl_path, 'w') as f:
            f.write(mtl_content)

        # Create dummy PNG files
        for png_file in png_files:
            png_path = os.path.join(srcdir, png_file)
            with open(png_path, 'wb') as f:
                f.write(os.urandom(1024))  # 1KB random content

        # Convert OBJ to DAE
        obj_to_dae(obj_path, dae_path)

        # Check if DAE file is created
        assert os.path.exists(dae_path)

        # Check if PNG files are copied
        for png_file in png_files:
            copied_png_path = os.path.join(dstdir, png_file)
            assert os.path.exists(copied_png_path)


def test_dae_to_kml():

    with tempfile.TemporaryDirectory() as tempdir:
        dae_path = os.path.join(tempdir, "model.dae")
        kml_dir = tempdir

        # Create a dummy DAE file
        with open(dae_path, 'w') as f:
            f.write("<COLLADA></COLLADA>")

        lat, lon, alt = 48.25, 25.9, 100.0

        dae_to_kml(dae_path, lat, lon, alt, kml_dir)

        kml_path = os.path.join(kml_dir, "model.kml")
        assert os.path.exists(kml_path)

        # Verify KML content
        with open(kml_path, 'r') as f:
            kml_content = f.read()
            soup = bs4.BeautifulSoup(kml_content, 'xml')
            root = soup.find('kml')
            assert root is not None
            model = soup.find('Model')
            location = model.find('Location')
            latitude = float(location.find('latitude').text)
            longitude = float(location.find('longitude').text)
            altitude = float(location.find('altitude').text)

            assert abs(latitude - lat) < 0.0001
            assert abs(longitude - lon) < 0.0001
            assert abs(altitude - alt) < 0.0001


def test_obj_to_kmz():
    # Use mocks for read_georef, obj_to_dae, dae_to_kml
    import os
    from unittest import mock
    from objtokmz import obj_to_kmz as obj_to_kmz_func  

    with tempfile.TemporaryDirectory() as tempdir:
        obj_path = os.path.join(tempdir, "model.obj")
        georef_path = os.path.join(tempdir, "georef.txt")
        kmz_path = os.path.join(tempdir, "output.kmz")

        # Create dummy OBJ file
        with open(obj_path, 'w') as f:
            f.write("# Dummy OBJ content")

        # Create dummy georef file
        with open(georef_path, 'w') as f:
            f.write("WGS84 UTM 35N\n418574 5345544\n")

        with mock.patch('objtokmz.read_georef', return_value=(25.9, 48.25, 100.0)) as mock_read_georef, \
             mock.patch('objtokmz.obj_to_dae') as mock_obj_to_dae, \
             mock.patch('objtokmz.dae_to_kml') as mock_dae_to_kml:
            obj_to_kmz_func(obj_path, georef_path, kmz_path)
            mock_read_georef.assert_called_once_with(georef_path)
            mock_obj_to_dae.assert_called_once_with(obj_path, mock.ANY)
            mock_dae_to_kml.assert_called_once_with(mock.ANY, 48.25, 25.9, 100.0, mock.ANY)

        # Check if KMZ file is created
        assert os.path.exists(kmz_path)
