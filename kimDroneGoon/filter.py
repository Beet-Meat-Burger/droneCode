import geopandas as gpd
import numpy as np
from scipy.ndimage import label
from shapely.geometry import Point

class PopulationFilters:
    @staticmethod
    def threshold_filter(gdf, min_pop=500):
        """Removes any grid squares below the population threshold."""
        return gdf[gdf['pop'] >= min_pop].copy()

    @staticmethod
    def size_filter(gdf, min_cells=4):
        """
        Removes 'islands' that don't have enough contiguous cells.
        Expects a GDF with 'island_id' column.
        """
        if gdf.empty or 'island_id' not in gdf.columns:
            return gdf
        
        counts = gdf['island_id'].value_counts()
        valid_islands = counts[counts >= min_cells].index
        return gdf[gdf['island_id'].isin(valid_islands)].copy()

    @staticmethod
    def distance_suppression(gdf, min_dist_meters=800):
        """
        Ensures markers are spaced out. 
        Keeps the highest population point within the radius.
        """
        if gdf.empty:
            return gdf

        # 1. Project to HK Metric system (EPSG:2326) or Web Mercator (EPSG:3857) for meters
        gdf_metric = gdf.to_crs(epsg=3857).sort_values('pop', ascending=False)
        
        kept_indices = []
        while not gdf_metric.empty:
            # Take the densest point
            best = gdf_metric.iloc[0]
            kept_indices.append(best.name)
            
            # Remove everything within the radius
            is_far = gdf_metric.distance(best.geometry) > min_dist_meters
            gdf_metric = gdf_metric[is_far]
            
        return gdf.loc[kept_indices].copy()

    @staticmethod
    def sandbox_filter(gdf, sandbox_zones):
        """Keeps only points that fall inside your allowed sandbox polygons."""
        if gdf.empty or sandbox_zones.empty:
            return gdf
        # Spatial join to keep points within polygons
        return gpd.sjoin(gdf, sandbox_zones, predicate='within')
