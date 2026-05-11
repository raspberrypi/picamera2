import time

# Example showing how to save a DNG file from Picamera2 using the muimg package.
# muimg should give faster performance than the default DNG writer (unless your
# storage medium is proving to be the bottleneck).
#
# NOTE: please check https://github.com/mu-files/mu-image/blob/main/muimg/README.md for
# installation and licensing information (should be free to use except for large
# commercial companies, but please confirm this for yourselves).
from picamera2 import Picamera2


def muimg_save_dng(output, request):
    import re

    import numpy as np
    from muimg import IfdDataSpec, PageEncoding, write_dng
    from muimg.tiff_metadata import MetadataTags
    from tifffile import COMPRESSION, PHOTOMETRIC

    from picamera2 import MappedArray

    picam2 = request.picam2
    metadata = request.get_metadata()
    raw_config = picam2.camera_configuration()['raw']
    match = re.match(r"^S(Y|RGGB|GRBG|GBRG|BGGR)(10|12|14|16)$", raw_config['format'])
    if not match:
        raise ValueError(f"Invalid raw format {raw_config['format']}")
    pattern = match.group(1)
    bit_depth = int(match.group(2))
    width, height = raw_config['size']
    black_levels = [val >> (16 - bit_depth) for val in metadata['SensorBlackLevels']]

    tags = MetadataTags()
    tags.add_tag("ISOSpeedRatings", [int(metadata['AnalogueGain'] * 100)])
    tags.add_tag("ExposureTime", [[1, int(1 / (metadata['ExposureTime'] * 0.000001))]])
    tags.add_tag("ImageWidth", width)
    tags.add_tag("ImageLength", height)
    tags.add_tag("RawDataUniqueID", str(metadata["SensorTimestamp"]).encode("ascii"))
    tags.add_tag("Orientation", 1)
    tags.add_tag("SamplesPerPixel", 1)
    tags.add_tag("BitsPerSample", bit_depth)
    tags.add_tag("WhiteLevel", ((1 << bit_depth) - 1))
    tags.add_tag("BaselineExposure", [[1, 1]])
    tags.add_tag("Make", "RaspberryPi")
    tags.add_tag("Model", picam2.camera_properties['Model'])
    tags.add_tag("ProfileName", "mu-files / Picamera2 profile")
    tags.add_tag("ProfileEmbedPolicy", [3])

    if pattern != "Y":
        # Colour Bayer sensor
        gain_r, gain_b = metadata["ColourGains"]
        gain_matrix = np.array([[gain_r, 0, 0], [0, 1.0, 0], [0, 0, gain_b]])
        as_shot_neutral = [1 / gain_r, 1, 1 / gain_b]

        ccm = np.array(metadata["ColourCorrectionMatrix"]).reshape(3, 3)
        # This maxtrix from http://www.brucelindbloom.com/index.html?Eqn_RGB_XYZ_Matrix.html
        rgb_to_xyz = np.array(
            [[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]]
        )
        ccm1 = np.linalg.inv(rgb_to_xyz.dot(ccm).dot(gain_matrix)).flatten().tolist()

        tags.add_tag("BlackLevelRepeatDim", [2, 2])
        tags.add_tag("BlackLevel", black_levels)
        tags.add_tag("PhotometricInterpretation", PHOTOMETRIC.CFA)
        tags.add_tag("CFARepeatPatternDim", [2, 2])
        tags.add_tag("CFAPattern", pattern)
        tags.add_tag("ColorMatrix1", ccm1)
        tags.add_tag("AsShotNeutral", as_shot_neutral)
    else:
        # Monochrome raw sensor.
        tags.add_tag("BlackLevelRepeatDim", [1, 1])
        tags.add_tag("BlackLevel", [black_levels[0]])
        tags.add_tag("PhotometricInterpretation", PHOTOMETRIC.LINEAR_RAW)

    encoding = PageEncoding(compression=COMPRESSION.NONE, compression_args=None, tile_size=None)

    with MappedArray(request, 'raw') as m:
        data_spec = IfdDataSpec(
            data=m.array[:, : 2 * width].view(np.uint16),
            photometric="CFA",
            bits_per_sample=bit_depth,
            cfa_pattern=pattern,
            encoding=encoding,
            extratags=tags,
        )

        write_dng(destination_file=output, ifd0_spec=data_spec, num_compression_workers=1)


picam2 = Picamera2()
raw_config = {'format': 'SBGGR12'}
config = picam2.create_still_configuration(raw=raw_config, buffer_count=2)
picam2.start(config)
time.sleep(1)

with picam2.captured_request() as request:
    muimg_save_dng("test.dng", request)
