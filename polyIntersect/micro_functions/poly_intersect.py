import polyIntersect.micro_functions.utils as u

from dask.multiprocessing import get
from osgeo import ogr
import geojson as gj
from geomet import wkt as WKT

__all__ = ['json2ogr', 'ogr2json', 'dissolve', 'intersect', 'buffer_to_dist',
           'get_area_overlap']


def json2ogr(json):
    '''
    Convert geojson object to GDAL geometry
    '''
    geoms = ogr.Geometry(ogr.wkbMultiPolygon)
    for feature in gj.loads(json)['features']:
        geom = ogr.CreateGeometryFromWkt(WKT.dumps(feature['geometry']))
        geoms.AddGeometry(geom)
    geoms_prj = u.project(geoms, geoms.Centroid(), 'to-custom')
    return geoms_prj


def ogr2json(geom):
    '''
    Convert GDAL geometry to geojson object
    '''
    return geom.ExportToJson()


def dissolve(geom, field=None):
    '''
    Dissolve a set of geometries on a field, or dissolve fully to a single
    feature if no field is provided

    *** this function doesn't allow dissolving based on field and can't
    find a function from osgeo - if we have a need for the field-based
    dissolve would need to implement something with Fiona/shapely/geopandas
    ^ add groupby functionality - group on either int or string
    '''
    return geom.UnionCascaded()


def intersect(geom1, geom2):
    '''
    Intersect two geometries
    '''
    return geom1.Intersection(geom2)


def buffer_to_dist(geom, distance):
    '''
    Buffer a geometry with a given distance
    '''
    return geom.Buffer(distance)


def get_area_overlap(geom, geom_intersect, groupby=None):
    '''
    Calculate the area of a geometry and the percent overlap with an
    intersection of that geometry. Can calculate areas by category using
    a groupby field
    ^ add groupby functionality, convert math to numpy
    '''
    total_area = u.calculate_area(geom)
    intersection_area = u.calculate_area(geom_intersect)
    pct_overlap = 100.0 * intersection_area / total_area
    return (total_area, pct_overlap)


def is_valid(analysis_method):
    '''
    Validate that method exists
    '''
    return analysis_method in __all__


# example dask input for reference:
# graph = {'convert_aoi': (json2ogr, user_json),
#          'convert_intersect': (json2ogr, intersect_json),
#          'dissolve_aoi': (dissolve, 'convert_aoi'),
#          'buffer_aoi': (buffer_to_dist, 'dissolve_aoi', user_dist),
#          'intersect_aoi': (intersect, 'buffer_aoi', 'convert_intersect'),
#          'area_overlap': (get_area_overlap, 'convert_aoi', 'intersect_aoi'),
#          'convert_result': (ogr2json, 'intersect_aoi')}

def process_graph(graph):
    for func in graph.keys():
        assert is_valid(func)
    get(graph, graph.keys())


def intersect_area_geom(user_json, intersect_polys_json,
                        return_intersect_geom=False):
    try:
        # VALIDATE INPUT JSON FILES AND CONTAIN ONLY POLYGONS OR MULTIPOLYGONS
        u.verify_polygons(user_json)
        u.verify_polygons(intersect_polys_json)

        # DEFINE THE RESULT OBJECT
        result = {}

        # DISSOLVE USER POLYS AND CREATE 10KM AND 50KM BUFFERS
        user_polys = u.dissolve_to_single_feature(user_json)
        buffs_10km = u.buffer_and_dissolve_to_single_feature(user_json, 10000)
        buffs_50km = u.buffer_and_dissolve_to_single_feature(user_json, 50000)

        # DISSOLVE INTERSECTION POLYGONS TO A SINGLE FEATURE
        intersect_polys = u.dissolve_to_single_feature(intersect_polys_json)

        # CALCULATE INTERSECTIONS OF USER POLYGONS AND BUFFERS WITH POLYGONS
        intersection_user = user_polys.Intersection(intersect_polys)
        intersection_10km = buffs_10km.Intersection(intersect_polys)
        intersection_50km = buffs_50km.Intersection(intersect_polys)

        # IF RETURN INTERSECT GEOMETRY IS TRUE, POPULATE RESULTS WITH INTE
        # THIS IS DONE HERE BECAUSE THE u.calculate_area
        # FUNCTION MODIFIES THE GEOMETRY OBJECTS

        if return_intersect_geom:
            result['intersect_geom_user'] = intersection_user.ExportToJson()
            result['intersect_geom_10km'] = intersection_10km.ExportToJson()
            result['intersect_geom_50km'] = intersection_50km.ExportToJson()

        # CALCULATE AREA OF USER POLYS AND BUFFERS
        user_area_ha = u.calculate_area(user_polys)
        buff_10km_ha = u.calculate_area(buffs_10km)
        buff_50km_ha = u.calculate_area(buffs_50km)

        #   CALCULATE AREA OF INTERSECTIONS =====#####
        user_area_intersection_ha = u.calculate_area(intersection_user)
        buff_10km_intersection_ha = u.calculate_area(intersection_10km)
        buff_50km_intersection_ha = u.calculate_area(intersection_50km)

        #   CALCULATE % OVERLAP =====#####
        pct_overlap_user = user_area_intersection_ha / user_area_ha * 100
        pct_overlap_10km = buff_10km_intersection_ha / buff_10km_ha * 100
        pct_overlap_50km = buff_50km_intersection_ha / buff_50km_ha * 100

        #   POPULATE RESULTS WITH AREAS =====#####
        result['areaHa_user'] = user_area_ha
        result['areaHa_10km'] = buff_10km_ha
        result['areaHa_50km'] = buff_50km_ha
        result['pct_overlap_user'] = pct_overlap_user
        result['pct_overlap_10km'] = pct_overlap_10km
        result['pct_overlap_50km'] = pct_overlap_50km

        return result
    except:
        raise
