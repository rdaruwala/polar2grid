"""Functions and mappings for taking rempapped VIIRS data and
rescaling it to a useable range from 0 to 255 to be compatible
and "pretty" with AWIPS.

WARNING: A scaling function is not guarenteed to not change the
original data array passed.  If fact, it is faster in most cases
to change the array in place.

Author: David Hoese,davidh,SSEC
"""
import os
import sys
import logging
import numpy

from adl_guidebook import K_REFLECTANCE,K_RADIANCE,K_BTEMP

log = logging.getLogger(__name__)

def _make_lin_scale(m, b):
    def linear_scale(img, *args, **kwargs):
        log.debug("Running 'linear_scale' with (m: %f, b: %f)..." % (m,b))
        # Faster than assigning
        numpy.multiply(img, m, img)
        numpy.add(img, b, img)
        return img
    return linear_scale

def passive_scale(img, *args, **kwargs):
    """When there is no rescaling necessary or it hasn't
    been determined yet, use this function.
    """
    log.debug("Running 'passive_scale'...")
    return img

def sqrt_scale(img, *args, **kwargs):
    log.debug("Running 'sqrt_scale'...")
    print img.min(), img.max()
    # FIXME: Remove this line when unscaled stuff works
    #numpy.divide(img, 65536.0, img)
    print img.min(), img.max()
    numpy.multiply(img, 100.0, img)
    print img.min(), img.max()
    numpy.sqrt(img, out=img)
    print img.min(), img.max()
    numpy.multiply(img, 25.5, img)
    print img.min(), img.max()
    numpy.round(img, out=img)
    print img.min(), img.max()
    return img

def bt_scale(img, *args, **kwargs):
    log.debug("Running 'bt_scale'...")
    print img.min(),img.max()
    high_idx = img >= 242.0
    low_idx = img < 242.0
    z_idx = img == 0
    img[high_idx] = 660 - (2*img[high_idx])
    img[low_idx] = 418 - img[low_idx]
    img[z_idx] = 0
    print img.min(),img.max()
    return img

def dnb_scale(img, *args, **kwargs):
    """
    This scaling method uses histogram equalization to flatten the image levels across any given section_masks.
    section_masks is expected to be a multi dimensional array. The first dimension is an array of different masks
    and the remaining dimesions must match img. This reflects the fact that section_masks[0] would yield a mask that
    can be applied directly to img. It is expected that there will be at least one mask (ie. one entry in the first
    dimension) in section_masks that represents data which is not fill data.
    A histogram equalization will be performed separately for each part of the img defined by a mask in section_masks.
    
    FUTURE: Right now section_masks is not being filled in by the calling code, so there's some temporary code that
    will create a testing mask.
    """

    log.debug("Running 'dnb_scale'...")
    # TODO, remove this code when the mask is properly filled in
    section_masks = [img != -999]
    # TODO, should this be input via params or a constant?
    num_bins      = 256
    
    # perform a histogram equalization for each mask
    for mask_index in range(len(section_masks)) :
        current_mask              = section_masks[mask_index]
        temp_histogram, temp_bins = numpy.histogram(img[current_mask], num_bins, normed=True)
        cumulative_dist_function  = temp_histogram.cumsum() # calculate the cumulative distribution function
        cumulative_dist_function  = (num_bins - 1) * cumulative_dist_function / cumulative_dist_function[-1] # normalize our function
        
        # linearly interpolate using the distribution function to get the new values
        img[current_mask] = numpy.interp(img[current_mask], temp_bins[:-1], cumulative_dist_function)
    
    return img

M_SCALES = {
        1  : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale},
        2  : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale},
        3  : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale},
        4  : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale},
        5  : {K_REFLECTANCE:sqrt_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale},
        6  : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale},
        7  : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale},
        8  : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale},
        9  : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale},
        10 : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale},
        11 : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale},
        12 : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale},
        13 : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:bt_scale},
        14 : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale},
        15 : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:bt_scale},
        16 : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale}
        }

I_SCALES = {
        1  : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale},
        2  : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale},
        3  : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale},
        4  : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale},
        5  : {K_REFLECTANCE:passive_scale, K_RADIANCE:passive_scale, K_BTEMP:passive_scale}
        }

DNB_SCALES = {
        0 : {K_REFLECTANCE:passive_scale, K_RADIANCE:dnb_scale, K_BTEMP:passive_scale}
        }

SCALES = {
        "M"  : M_SCALES,
        "I"  : I_SCALES,
        "DNB" : DNB_SCALES
        }

def rescale(img, kind="M", band=5, data_kind=K_RADIANCE, **kwargs):
    band = int(band) # If it came from a filename, it was a string

    if kind not in SCALES:
        log.error("Unknown kind %s, only know %r" % (kind, SCALES.keys()))
        raise ValueError("Unknown kind %s, only know %r" % (kind, SCALES.keys()))

    kind_scale = SCALES[kind]

    if band not in kind_scale:
        log.error("Unknown band %s for kind %s, only know %r" % (band, kind, kind_scale.keys()))
        raise ValueError("Unknown band %s for kind %s, only know %r" % (band, kind, kind_scale.keys()))

    dkind_scale = kind_scale[band]

    if data_kind not in dkind_scale:
        log.error("Unknown data kind %s for kind %s band %s" % (data_kind, kind, band))
        raise ValueError("Unknown data kind %s for kind %s band %s" % (data_kind, kind, band))

    scale_func = dkind_scale[data_kind]
    img = scale_func(img, kind=kind, band=band, data_kind=data_kind, **kwargs)
    return img

def rescale_and_write(img_file, output_file, *args, **kwargs):
    # TODO: Open img file
    img = None
    new_img = rescale(img, *args, **kwargs)
    # TODO: Write new_img to output_file

def main():
    import optparse
    usage = """%prog [options] <input.fbf_format> <output.fbf_format> <band>"""
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('-v', '--verbose', dest='verbosity', action="count", default=0,
                    help='each occurrence increases verbosity 1 level through ERROR-WARNING-INFO-DEBUG')
    options,args = parser.parse_args()

    levels = [logging.ERROR, logging.WARN, logging.INFO, logging.DEBUG]
    logging.basicConfig(level = levels[min(3, options.verbosity)])

    return rescale_and_write(*args)

if __name__ == "__main__":
    sys.exit(main())

