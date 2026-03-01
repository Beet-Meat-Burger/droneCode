import folium
import numpy as np
from shapely.geometry import LineString, Point, box
import branca.colormap as cm
import geopandas as gpd
from ortools.constraint_solver import routing_enums_pb2, pywrapcp


class visualizer:
    def __init__(self, dataLoader):
        self.loader = dataLoader
        # High-contrast dark background to make red 'pop'
        self.map = folium.Map(
            location=[22.3193, 114.1694], 
            zoom_start=11, 
            tiles="CartoDB positron" 
        )

    def addPopulationHeatmap(self, samplingStep=1, valTh=0.1):
        popData = self.loader.popRaster.read(1)
        transform = self.loader.popRaster.transform
        
        # 1. Define a High-Contrast Gradient (Dark Red to Neon Yellow)
        # Using a StepColormap for 'buckets' or LinearColormap for a smooth fade
        colorScale = cm.LinearColormap(
            colors=['#440000', '#FF0000', '#FF4500', '#FFFF00'], # Dark Red -> Bright Red -> Orange -> Yellow
            index=[1, 50, 500, 2500], # HK 100m density thresholds
            vmin=1, vmax=3000,
            caption='Population per 100m'
        )

        features = []
        rows, cols = popData.shape
        
        for r in range(0, rows, samplingStep):
            for c in range(0, cols, samplingStep):
                val = float(popData[r, c])
                
                # We show everything > 0.1 to catch low-density areas
                if val > valTh:
                    # Get exact bounds for the 100m pixel
                    lonLeft, latTop = transform * (c, r)
                    lonRight, latBottom = transform * (c + samplingStep, r + samplingStep)
                    
                    # 2. Dynamic Opacity: Lower pop = Lower opacity (minimum 0.2 for visibility)
                    # Formula: scale 0.2 (low pop) to 0.9 (dense pop)
                    calcOpacity = 0.2 + (min(val, 1000) / 1000) * 0.7
                    
                    features.append({
                        "type": "Feature",
                        "properties": {
                            "pop": int(val),
                            "opacity": calcOpacity,
                            "color": colorScale(val)
                        },
                        "geometry": box(lonLeft, latBottom, lonRight, latTop).__geo_interface__
                    })

        # 3. Add to map with internal property mapping
        folium.GeoJson(
            {"type": "FeatureCollection", "features": features},
            name="Population Heatmap",
            style_function=lambda x: {
                'fillColor': x['properties']['color'],
                'color': 'none', # No borders for a smooth heatmap look
                'fillOpacity': x['properties']['opacity']
            },
            tooltip=folium.GeoJsonTooltip(fields=['pop'], aliases=['People:'])
        ).add_to(self.map)
        
        self.map.add_child(colorScale)

    def addStrategicPeaks(self):
    
        islands_gdf, peaks_gdf, quiet_gdf = self.loader.getStrategicIslands(threshold=500, min_cells=5)

        for _, peak in peaks_gdf.iterrows():
            # A. Plot the Spike (The "Hot" spot)
            print(peak)
            folium.Marker(
                location=[peak.geometry.y, peak.geometry.x],
                popup=f"Spike: {int(peak['pop'])}",
                icon=folium.Icon(color='red', icon='fire', prefix='fa')
            ).add_to(self.map)

            # B. Find and Plot top 3 Ranked Quiet Spots
            quiet_options = self.loader.findClosestQuietSpots(peak.geometry, quiet_threshold=500)

            for rank, spot in enumerate(quiet_options):
                # Rank 0 (Best) is dark blue, others are lighter
                color = "#0000FF" if rank == 0 else "#6699FF"
                
                folium.CircleMarker(
                    location=[spot['geometry'].y, spot['geometry'].x],
                    radius=6 - (rank * 1.5), # Smaller radius for lower ranks
                    color=color,
                    fill=True,
                    fill_opacity=0.8 - (rank * 0.2),
                    popup=f"Rank {rank+1} Quiet Spot\nPop: {int(spot['pop'])}"
                ).add_to(self.map)
            

    def addTspRouteToMap(self, peaks_gdf):
        # 1. Solve the TSP (returns list of indices)
        route_indices = self._get_tsp_route(peaks_gdf)
        
        # 2. Convert indices to (lat, lon) coordinates
        # IMPORTANT: Folium expects [lat, lon], while GeoPandas might be [lon, lat]
        route_coords = []
        for idx in route_indices:
            geom = peaks_gdf.iloc[idx].geometry
            route_coords.append([geom.y, geom.x])

        # 3. Draw the Path
        folium.PolyLine(
            locations=route_coords,
            color="#E91E63", # A vibrant pink/red for the path
            weight=4,
            opacity=0.7,
            tooltip="Optimized TSP Route",
            dash_array='10, 10' # Optional: dashed line look
        ).add_to(self.map)
        
        # 4. Add Directional Markers (Optional)
        for i, idx in enumerate(route_indices[:-1]):
            geom = peaks_gdf.iloc[idx].geometry
            folium.CircleMarker(
                location=[geom.y, geom.x],
                radius=3,
                color='white',
                fill=True,
                popup=f"Stop {i+1}"
            ).add_to(self.map)

    def _get_tsp_route(self, gdf):
        num_locs = len(gdf)
        if num_locs < 2: return []
        
        # Generate Distance Matrix (Euclidean for simplicity)
        dist_matrix = []
        for i in range(num_locs):
            row = [int(gdf.iloc[i].geometry.distance(gdf.iloc[j].geometry) * 1000) 
                for j in range(num_locs)]
            dist_matrix.append(row)

        manager = pywrapcp.RoutingIndexManager(num_locs, 1, 0)
        routing = pywrapcp.RoutingModel(manager)

        def dist_callback(from_idx, to_idx):
            return dist_matrix[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)]

        callback_index = routing.RegisterTransitCallback(dist_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(callback_index)

        search_params = pywrapcp.DefaultRoutingSearchParameters()
        search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        
        solution = routing.SolveWithParameters(search_params)
        
        # Extract order
        route = []
        index = routing.Start(0)
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        route.append(manager.IndexToNode(index)) # Loop back to start
        return route


    def addInterIslandCorridors(self):
        from kimDroneGoon.routing_logic import StealthRouter
        router = StealthRouter(self.loader.popRaster)
        islands_gdf, peaks_gdf, quiet_gdf = self.loader.getStrategicIslands(threshold=500, min_cells=5)
        # Example: Link every peak to the quietest spot on the NEAREST other island
        for idx, peak in peaks_gdf.iterrows():
            # 1. Find potential target (e.g., a quiet spot on a different island)
            # For now, let's assume you have a list of 'quiet_spots'
            quiet_spots = self.loader.findClosestQuietSpots(peak.geometry, quiet_threshold=500, top_n=1)
            for target in quiet_spots:
    # Now 'target' is a dictionary, so use target['geometry'] 
    # instead of target.geometry
                path_geom, cost = router.find_stealth_snake(peak.geometry, target['geometry'])

                
                if path_geom:
                    # 2. Plot the 'Snake' on the map
                    # The line will naturally bend around high-density pixels
                    folium.GeoJson(
                        path_geom.__geo_interface__,
                        style_function=lambda x: {'color': 'green', 'weight': 2, 'opacity': 0.7},
                        tooltip=f"Stealth Path Cost: {int(cost)} pop-units"
                    ).add_to(self.map)


    

    def addHeatmapPeaks(self, threshold=500):
        islands, peaks = self.loader.getIslandPeaks(threshold=threshold)

        # Mark the 'capital' of every island
        for _, peak in peaks.iterrows():
            folium.Marker(
                location=[peak.geometry.y, peak.geometry.x],
                popup=f"Island #{peak['island_id']} Peak: {int(peak['pop'])}",
                icon=folium.Icon(color='orange', icon='info-sign')
            ).add_to(self.map)


    

    def addLandUseLayer(self):
        # Using a neon-blue for high contrast against the red pop and dark map
        data = self.loader.landUseRaster.read(1)
        # Bounds logic from previous step
        # ... (Refer to previous ImageOverlay code for bounds) ...
        folium.raster_layers.ImageOverlay(
            image=data,
            bounds=self._get_raster_bounds(self.loader.landUseRaster),
            colormap=lambda x: (0, 0.8, 1, 0.3) if x > 0 else (0,0,0,0),
            name="Land Use Context"
        ).add_to(self.map)

    def addSandboxZones(self):
        # Bright yellow/green for allowed zones
        folium.GeoJson(
            self.loader.sandboxZones,
            name="Allowed Sandbox Zones",
            style_function=lambda x: {
                'fillColor': '#00FF00',
                'color': '#FFFFFF',
                'weight': 3,
                'fillOpacity': 0.2,
            },
            tooltip=folium.GeoJsonTooltip(fields=['name'])
        ).add_to(self.map)

    def addStrategicHotspots(self, neighborhood=1000): # ~700m search radius
        # Get the dispersed hotspots
        gdf = self.loader.findLocalHotspots(neighborhood_size=neighborhood)
        
        for _, row in gdf.iterrows():
            coords = [row.geometry.y, row.geometry.x]
            
            # Use a distinctive 'Pulse' or different icon for these strategic peaks
            folium.Circle(
                location=coords,
                radius=150, # Show the 'influence' area
                color='#00FFFF', # Cyan for 'Strategic Peak'
                weight=2,
                fill=True,
                fill_opacity=0.4,
                tooltip=f"Local Peak: {int(row['pop'])} people"
            ).add_to(self.map)

    def _get_raster_bounds(self, src):
        from rasterio.warp import transform_bounds
        bounds = src.bounds
        left, bottom, right, top = transform_bounds(src.crs, 'EPSG:4326', *bounds)
        return [[bottom, left], [top, right]]


    def render(self, fileName="hk_lae_model.html"):
        folium.LayerControl().add_to(self.map)
        self.map.save(fileName)
        return self.map


    def peaksRecipe(self):
        from kimDroneGoon.filter import PopulationFilters as PF

        # 1. Load the data
        raw_grid = self.loader.get_raw_grid_gdf()

        # 2. Apply the "Island" Filter (Keep only dense areas)
        islands = PF.threshold_filter(raw_grid, min_pop=500)
        islands = PF.size_filter(islands, min_cells=100)

        # 3. Create the "Strategic Markers" (Distance Filter)
        # We apply this to the islands we already found
        markers = PF.distance_suppression(islands, min_dist_meters=1000)

        for _, m in markers.iterrows():
            folium.Marker([m.geometry.y, m.geometry.x], icon=folium.Icon(color='red')).add_to(self.map)

    def calculate_route_distance(self, route_points_gdf):
        """
        Takes a GeoDataFrame of points in the order of the TSP route
        and returns the total distance in meters.
        """
        if route_points_gdf is None or len(route_points_gdf) < 2:
            return 0.0

        # 1. Project to Meters (EPSG:3857 is standard for web distance)
        # Using a local UTM zone would be even more precise, 
        # but 3857 is usually sufficient for drone paths.
        gdf_meters = route_points_gdf.to_crs(epsg=3857)

        # 2. Create a LineString from the points to get the total length
        # We include the first point at the end to close the TSP loop
        points = list(gdf_meters.geometry)
        points.append(points[0]) # Close the circuit
        
        route_line = LineString(points)
        total_meters = route_line.length

        # 3. Print Results
        print("-" * 30)
        print(f"DRONE MISSION STATS")
        print(f"Total Distance: {total_meters:.2f} meters")
        print(f"Total Distance: {total_meters / 1000:.2f} km")
        print("-" * 30)

        return total_meters


    def addOptimizedDronePath(self):
        # 1. Fetch and Clean Data
        _, _, quiet_gdf = self.loader.getStrategicIslands(threshold=500, min_cells=5)

        if quiet_gdf is None or len(quiet_gdf) < 3:
            print("Not enough points for a TSP route.")
            return

        # Force a clean integer index (0, 1, 2...)
        df = quiet_gdf.reset_index(drop=True)
        num_locs = len(df)
        
        # Identify the population column name (it might be 'pop' or something else)
        pop_col = 'pop' if 'pop' in df.columns else df.columns[0] # Fallback to first col

        # 2. Build Cost Matrix using .iloc (positional only)
        matrix = []
        for i in range(num_locs):
            row = []
            geom_i = df.iloc[i].geometry
            for j in range(num_locs):
                if i == j:
                    row.append(0)
                else:
                    geom_j = df.iloc[j].geometry
                    dist = geom_i.distance(geom_j)
                    
                    # Get population safely using .iloc
                    pop_val = df.iloc[j][pop_col]
                    
                    # Cost Calculation (Scaled for OR-Tools)
                    cost = int((dist * 1.0 + pop_val * 5.0) * 1000)
                    row.append(cost)
            matrix.append(row)

        # 3. OR-Tools Setup
        manager = pywrapcp.RoutingIndexManager(num_locs, 1, 0)
        routing = pywrapcp.RoutingModel(manager)

        def transit_callback(from_idx, to_idx):
            return matrix[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)]

        cb_index = routing.RegisterTransitCallback(transit_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(cb_index)

        # 4. Solve
        search_params = pywrapcp.DefaultRoutingSearchParameters()
        search_params.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
        
        solution = routing.SolveWithParameters(search_params)

        # 5. Build PolyLine Coordinates
        if solution:
            route_coords = []
            index = routing.Start(0)
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                # Use .iloc to get geometry by position
                pt = df.iloc[node].geometry
                route_coords.append([pt.y, pt.x])
                index = solution.Value(routing.NextVar(index))
            
            # Connect back to start
            route_coords.append(route_coords[0])

            ordered_indices = []
            index = routing.Start(0)
            while not routing.IsEnd(index):
                ordered_indices.append(manager.IndexToNode(index))
                index = solution.Value(routing.NextVar(index))

            # Create a GDF of the spots in the OPTIMIZED order
            ordered_gdf = quiet_gdf.iloc[ordered_indices]

            # CALL THE DISTANCE FUNCTION
            self.calculate_route_distance(ordered_gdf)
            self.print_route_legs(ordered_gdf)


            folium.PolyLine(
                locations=route_coords,
                color="green",
                weight=5,
                opacity=0.7
            ).add_to(self.map)
            print("TSP Path added successfully.")

    def print_route_legs(self, ordered_gdf):
        """
        Calculates and prints the distance of each individual leg in meters.
        """
        if ordered_gdf is None or len(ordered_gdf) < 2:
            print("Not enough points to calculate legs.")
            return

        # 1. Project to Meters for accurate measurement
        gdf_m = ordered_gdf.to_crs(epsg=3857)
        num_points = len(gdf_m)
        
        print(f"\n{'='*10} MISSION LEG REPORT {'='*10}")
        
        total_m = 0
        for i in range(num_points):
            # Current point
            p1 = gdf_m.iloc[i].geometry
            
            # Next point (loop back to start if at the end)
            next_idx = (i + 1) % num_points
            p2 = gdf_m.iloc[next_idx].geometry
            
            # Calculate leg distance
            leg_dist = p1.distance(p2)
            total_m += leg_dist
            
            # Print individual leg info
            start_label = f"Stop {i}"
            end_label = f"Stop {next_idx}" if next_idx != 0 else "Home (Return)"
            
            print(f"Leg {i+1}: {start_label} -> {end_label} | Distance: {leg_dist/1000:.2f}km")

        print(f"{'='*36}")
        print(f"TOTAL MISSION DISTANCE: {total_m:.2f}m")
        print(f"{'='*36}\n")
        
        return total_m
