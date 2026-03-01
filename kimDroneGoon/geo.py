import numpy as np
import rasterio
import geopandas as gpd
from shapely.geometry import Point
from scipy.ndimage import label, maximum_filter

class geodata:
    def __init__(self, popTiffPath, landUseTiffPath, sandboxGeojsonPath):
        # Load Rasters (WorldPop & Land Use)
        self.popRaster = rasterio.open(popTiffPath)
        self.landUseRaster = rasterio.open(landUseTiffPath)
        
        # Load Vector (Sandbox Zones)
        self.sandboxZones = gpd.read_file(sandboxGeojsonPath)
        
        # Ensure all data uses standard GPS coordinates (WGS84)
        if self.sandboxZones.crs != "EPSG:4326":
            self.sandboxZones = self.sandboxZones.to_crs("EPSG:4326")

    def getPopulationDensity(self, lat, lng):
        """Returns the population count from the 100m WorldPop grid."""
        # Use rasterio's index method to find the pixel for the coordinates
        row, col = self.popRaster.index(lng, lat)
        # Read a 1x1 window to get the specific pixel value
        data = self.popRaster.read(1, window=((row, row+1), (col, col+1)))
        return float(data[0][0]) if data.size > 0 else 0.0

    def getLandUseCategory(self, lat, lng):
        """Returns the integer category ID from the HK Land Use raster."""
        row, col = self.landUseRaster.index(lng, lat)
        data = self.landUseRaster.read(1, window=((row, row+1), (col, col+1)))
        return int(data[0][0]) if data.size > 0 else -1

    def isWithinSandbox(self, lat, lng):
        """Checks if a point is inside any allowed Sandbox polygon."""
        point = Point(lng, lat)
        # Use geopandas .contains() to check point-in-polygon
        return self.sandboxZones.contains(point).any()
    
    
    def findLocalHotspots(self, neighborhood_size=5, min_pop=50):
        """
        neighborhood_size: 5 means a 5x5 window (500m x 500m in WorldPop).
        min_pop: ignore peaks that are locally high but globally tiny.
        """
        pop_data = self.popRaster.read(1)
        
        # 1. Find the maximum value in every 5x5 neighborhood
        local_max = maximum_filter(pop_data, size=neighborhood_size)
        
        # 2. A pixel is a hotspot ONLY if it equals the local max AND beats min_pop
        mask = (pop_data == local_max) & (pop_data > min_pop)
        
        rows, cols = np.where(mask)
        
        # Get all coords at once
        lons, lats = self.popRaster.xy(rows, cols)
        
        # Create a list of Points
        geometry = [Point(lon, lat) for lon, lat in zip(lons, lats)]
        
        # Create GeoDataFrame immediately
        gdf = gpd.GeoDataFrame({'pop': pop_data[rows, cols]}, geometry=geometry, crs=self.popRaster.crs)
        
        # Use a spatial join or filter to check the Sandbox
        # This is MUCH faster than running self.isWithinSandbox in a loop
        if not self.sandboxZones.empty:
            # Ensure CRS match for the filter
            if gdf.crs != self.sandboxZones.crs:
                gdf = gdf.to_crs(self.sandboxZones.crs)
            
            # Filter: keep only points that are within any sandbox zone
            gdf = gdf[gdf.geometry.within(self.sandboxZones.unary_union)]

        return gdf

    def getIslandPeaks(self, threshold=500):
        """
        Groups adjacent pixels > threshold into unique 'islands'.
        Returns: A GeoDataFrame of all island pixels with an 'island_id',
                and a GeoDataFrame of just the peak pixel for EACH island.
        """
        pop_data = self.popRaster.read(1)
        
        # 1. Create a binary mask of high-density areas
        mask = (pop_data > threshold).astype(int)
        
        # 2. Label connected components (islands)
        # structure=np.ones((3,3)) includes diagonals
        labeled_array, num_features = label(mask, structure=np.ones((3,3)))
        
        if num_features == 0:
            return gpd.GeoDataFrame(), gpd.GeoDataFrame()

        # 3. Extract pixel data
        rows, cols = np.where(labeled_array > 0)
        island_ids = labeled_array[rows, cols]
        pops = pop_data[rows, cols]
        lons, lats = self.popRaster.xy(rows, cols)
        
        # 4. Build the Master GeoDataFrame
        geometry = [Point(lon, lat) for lon, lat in zip(lons, lats)]
        all_islands_gdf = gpd.GeoDataFrame({
            'island_id': island_ids,
            'pop': pops
        }, geometry=geometry, crs=self.popRaster.crs)

        # 5. Identify the PEAK for EACH island
        # Group by island_id and get the index of the max population per group
        peak_indices = all_islands_gdf.groupby('island_id')['pop'].idxmax()
        peaks_gdf = all_islands_gdf.loc[peak_indices].copy()

        return all_islands_gdf, peaks_gdf

    def getStrategicIslands(self, threshold=500, min_cells=5, min_dist_meters=2000):
        from rasterio.windows import Window
        pop_data = self.popRaster.read(1)
        mask = (pop_data > threshold).astype(int)
        
        # 1. Label components to find islands
        labeled_array, num_features = label(mask, structure=np.ones((3,3)))
        if num_features == 0:
            return gpd.GeoDataFrame(), gpd.GeoDataFrame()

        # 2. Extract pixel data into GDF
        rows, cols = np.where(labeled_array > 0)
        all_pts = gpd.GeoDataFrame({
            'pop': pop_data[rows, cols],
            'island_id': labeled_array[rows, cols]
        }, geometry=[Point(lon, lat) for lon, lat in zip(*self.popRaster.xy(rows, cols))], crs="EPSG:4326")

        # 3. Size Filter: Keep only islands with enough cells
        counts = all_pts['island_id'].value_counts()
        valid_ids = counts[counts >= min_cells].index
        islands_gdf = all_pts[all_pts['island_id'].isin(valid_ids)].copy()

        if islands_gdf.empty:
            return islands_gdf, gpd.GeoDataFrame()

        # 4. Get the single highest peak for each unique island
        peaks_gdf = islands_gdf.sort_values('pop', ascending=False).drop_duplicates('island_id').copy()

        # 5. NEW: Distance Filtering (Strategic Elimination)
        # Convert to metric (EPSG:3857) to use meters for distance
        peaks_metric = peaks_gdf.to_crs(epsg=3857).sort_values('pop', ascending=False)
        final_peak_indices = []
        
        while not peaks_metric.empty:
            # Take the densest peak remaining
            current = peaks_metric.iloc[0]
            final_peak_indices.append(current.name)
            
            # Find all other peaks further than min_dist_meters away
            # This kills any neighboring markers within the radius
            distances = peaks_metric.geometry.distance(current.geometry)
            peaks_metric = peaks_metric[distances > min_dist_meters]

            # 6. Find the quietest spot near each final peak
        final_peaks_gdf = peaks_gdf.loc[final_peak_indices].copy()
        quiet_spots = []

        # Define search radius in pixels (e.g., 3x3 or 5x5)
        # WorldPop is roughly 100m/pixel at the equator
        pixel_radius = 1 

        for idx, peak in final_peaks_gdf.iterrows():
            # Get raster index of the peak
            row, col = self.popRaster.index(peak.geometry.x, peak.geometry.y)
            
            # Read a small window around the peak
            win = Window(col - pixel_radius, row - pixel_radius, 
                         pixel_radius * 2 + 1, pixel_radius * 2 + 1)
            
            # Read data and handle potential out-of-bounds
            window_data = self.popRaster.read(1, window=win, boundless=True, fill_value=np.nan)
            
            # Find the minimum (ignoring NaNs and NoData)
            if not np.all(np.isnan(window_data)):
                min_idx = np.nanargmin(window_data)
                rel_row, rel_col = np.unravel_index(min_idx, window_data.shape)
                
                # Convert relative window index back to global coordinates
                abs_row = row - pixel_radius + rel_row
                abs_col = col - pixel_radius + rel_col
                lon, lat = self.popRaster.xy(abs_row, abs_col)
                
                quiet_spots.append({
                    'peak_island_id': peak['island_id'],
                    'quiet_pop': window_data[rel_row, rel_col],
                    'geometry': Point(lon, lat)
                })

        quiet_gdf = gpd.GeoDataFrame(quiet_spots, crs="EPSG:4326")
        return islands_gdf, final_peaks_gdf, quiet_gdf

    def findQuietSpots(self, peak_geom, search_radius=10, quiet_threshold=50, top_n=3):
        """
        Finds the quietest (lowest population) spots near a population peak.
        Searches in expanding square rings to prioritize proximity.
        
        Args:
            peak_geom: Shapely Point geometry of the peak
            search_radius: Maximum pixels to search from peak (100m grid)
            quiet_threshold: Max population to qualify as "quiet"
            top_n: Number of quiet spots to return
            
        Returns:
            List of candidates sorted by [population, distance], limited to top_n
        """
        from rasterio.windows import Window
        
        row, col = self.popRaster.index(peak_geom.x, peak_geom.y)
        candidates = []
        seen_pixels = set([(row, col)])
        
        # Spiral outward in square rings
        for radius in range(1, search_radius + 1):
            ring_results = []
            
            # Check perimeter of square at distance 'radius'
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    # Only check edges of the square (not interior)
                    if abs(dr) != radius and abs(dc) != radius and radius > 1:
                        continue
                    
                    curr_row, curr_col = row + dr, col + dc
                    
                    if (curr_row, curr_col) in seen_pixels:
                        continue
                    seen_pixels.add((curr_row, curr_col))
                    
                    # Read pixel value
                    win = Window(curr_col, curr_row, 1, 1)
                    val = self.popRaster.read(1, window=win, boundless=True, fill_value=-1)[0, 0]
                    
                    if val >= 0 and val <= quiet_threshold:
                        lon, lat = self.popRaster.xy(curr_row, curr_col)
                        dist_m = peak_geom.distance(Point(lon, lat)) * 111_000  # degrees to meters
                        
                        ring_results.append({
                            'geometry': Point(lon, lat),
                            'pop': val,
                            'distance_m': dist_m
                        })
            
            # Sort this ring's results and add to candidates
            ring_results.sort(key=lambda x: (x['pop'], x['distance_m']))
            candidates.extend(ring_results)
            
            # Early exit if we have enough quiet spots
            if len(candidates) >= top_n:
                break
        
        # Final sort and return top N
        candidates.sort(key=lambda x: (x['pop'], x['distance_m']))
        return candidates[:top_n]

    def get_raw_grid_gdf(self):
        """Extracts the entire population raster into a GeoDataFrame of Points."""
        pop_data = self.popRaster.read(1)
        mask = pop_data > 0
        rows, cols = np.where(mask)
        lons, lats = self.popRaster.xy(rows, cols)
        
        # Label islands immediately so filters can use island_id
        labeled, _ = label(mask.astype(int), structure=np.ones((3,3)))
        
        return gpd.GeoDataFrame({
            'pop': pop_data[rows, cols],
            'island_id': labeled[rows, cols]
        }, geometry=[Point(lon, lat) for lon, lat in zip(lons, lats)], crs="EPSG:4326")

    def close(self):
        """Closes open raster files."""
        self.popRaster.close()
        self.landUseRaster.close()
