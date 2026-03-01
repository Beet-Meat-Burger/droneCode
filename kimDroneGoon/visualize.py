import folium
import numpy as np
from shapely.geometry import LineString, Point, box
import branca.colormap as cm
import geopandas as gpd
from ortools.constraint_solver import routing_enums_pb2, pywrapcp
import math


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
        """
        Marks population peaks with red fire icons.
        """
        islands_gdf, peaks_gdf, quiet_gdf = self.loader.getStrategicIslands(threshold=500, min_cells=5)

        for _, peak in peaks_gdf.iterrows():
            # Plot the Spike (The "Hot" spot)
            folium.Marker(
                location=[peak.geometry.y, peak.geometry.x],
                popup=f"Spike: {int(peak['pop'])}",
                icon=folium.Icon(color='red', icon='fire', prefix='fa')
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

    def getRandomPlaceOnDronePathPopNotZero(self, route_points_gdf):
        """
        Selects a random point along the drone path where population is not zero.
        """
        if route_points_gdf is None or len(route_points_gdf) == 0:
            return None

        # Sample population values from raster at each point location
        popData = self.loader.popRaster.read(1)
        transform = self.loader.popRaster.transform
        
        pop_values = []
        for _, row in route_points_gdf.iterrows():
            x, y = row.geometry.x, row.geometry.y
            col, row_idx = ~transform * (x, y)
            col, row_idx = int(col), int(row_idx)
            if 0 <= row_idx < popData.shape[0] and 0 <= col < popData.shape[1]:
                pop_values.append(float(popData[row_idx, col]))
            else:
                pop_values.append(0.0)
        
        route_points_gdf = route_points_gdf.copy()
        route_points_gdf['pop'] = pop_values
        
        # Filter to points with population > 0
        valid_points = route_points_gdf[route_points_gdf['pop'] > 0]

        if valid_points.empty:
            print("No valid points with population > 0 found on the route.")
            return None

        # Randomly select one of the valid points
        random_point = valid_points.sample(n=1).iloc[0]
        return random_point.geometry.y, random_point.geometry.x

    

    def getOptimizedDronePath(self):
        """
        Computes the optimized TSP route and returns the ordered GeoDataFrame.
        Used by addOptimizedDronePath() for visualization and other functions.
        
        Returns:
            GeoDataFrame with points ordered along the TSP route, or None if not enough points
        """
        # 1. Fetch and Clean Data
        _, _, quiet_gdf = self.loader.getStrategicIslands(threshold=500, min_cells=5)

        if quiet_gdf is None or len(quiet_gdf) < 3:
            print("Not enough points for a TSP route.")
            return None

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

        # 5. Extract ordered route and return as GeoDataFrame
        if solution:
            ordered_indices = []
            index = routing.Start(0)
            while not routing.IsEnd(index):
                ordered_indices.append(manager.IndexToNode(index))
                index = solution.Value(routing.NextVar(index))

            # Return GDF of the spots in the OPTIMIZED order
            ordered_gdf = quiet_gdf.iloc[ordered_indices]
            return ordered_gdf
        
        return None

    def break_long_legs(self, waypoint_gdf, max_leg_km=10.0):
        """
        Inserts intermediate waypoints to break up legs longer than max_leg_km.
        Inserts at lowest population density points.
        
        Args:
            waypoint_gdf: GeoDataFrame of waypoints
            max_leg_km: Maximum leg distance before breaking (default 10 km)
            
        Returns:
            List of (lat, lng) tuples with inserted waypoints
        """
        waypoints = [(row.geometry.y, row.geometry.x) for _, row in waypoint_gdf.iterrows()]
        result_waypoints = []
        long_legs_found = []
        
        def haversine(lat1, lng1, lat2, lng2):
            """Calculate great-circle distance in km"""
            R = 6371  # Earth radius in km
            phi1 = math.radians(lat1)
            phi2 = math.radians(lat2)
            delta_phi = math.radians(lat2 - lat1)
            delta_lambda = math.radians(lng2 - lng1)
            
            a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            return R * c
        
        print(f"\n[*] Checking legs for distance > {max_leg_km} km...")
        
        for i in range(len(waypoints)):
            result_waypoints.append(waypoints[i])
            
            if i < len(waypoints) - 1:
                start_lat, start_lng = waypoints[i]
                end_lat, end_lng = waypoints[i + 1]
                
                leg_distance = haversine(start_lat, start_lng, end_lat, end_lng)
                
                if leg_distance > max_leg_km:
                    print(f"  Leg {i}→{i+1}: {leg_distance:.2f} km (LONG!)")
                    
                    # Calculate number of intermediate waypoints needed
                    num_intermediate = math.ceil(leg_distance / max_leg_km) - 1
                    print(f"    → Inserting {num_intermediate} intermediate waypoint(s)")
                    
                    # Sample along the leg
                    samples = []
                    for j in range(100):
                        t = j / 99.0
                        lat = start_lat + t * (end_lat - start_lat)
                        lng = start_lng + t * (end_lng - start_lng)
                        
                        try:
                            pop = self.loader.getPopulationDensity(lat, lng)
                        except:
                            pop = 0.0
                        
                        samples.append({'lat': lat, 'lng': lng, 'pop': pop, 't': t})
                    
                    # Find insertion points at evenly-spaced MIDDLE positions
                    # For N waypoints, place at t = 1/(N+1), 2/(N+1), ..., N/(N+1)
                    target_positions = [(i+1) / (num_intermediate + 1) for i in range(num_intermediate)]
                    insertion_points = []
                    search_radius = 0.15  # Look within ±15% around target position
                    
                    for target_t in target_positions:
                        # Find samples near this target position
                        nearby = [s for s in samples if abs(s['t'] - target_t) <= search_radius]
                        
                        if nearby:
                            # Among nearby samples, pick lowest population
                            best = min(nearby, key=lambda x: x['pop'])
                        else:
                            # Fallback: pick closest to target position
                            best = min(samples, key=lambda x: abs(x['t'] - target_t))
                        
                        insertion_points.append(best)
                    
                    # Already sorted by position due to target order
                    insertion_points = sorted(insertion_points, key=lambda x: x['t'])
                    
                    for pt in insertion_points:
                        result_waypoints.append((pt['lat'], pt['lng']))
                        print(f"      • Inserted at pop={pt['pop']:.0f}")
                    
                    long_legs_found.append({
                        'leg': (i, i+1),
                        'distance_km': leg_distance,
                        'intermediate': num_intermediate
                    })
                else:
                    print(f"  Leg {i}→{i+1}: {leg_distance:.2f} km ✓")
        
        # Print summary
        if long_legs_found:
            print(f"\n  Summary: {len(long_legs_found)} long leg(s) broken into {len(result_waypoints) - len(waypoints)} new waypoint(s)")
        else:
            print(f"\n  ✓ All legs within {max_leg_km} km limit")
        
        return result_waypoints, long_legs_found

    def addOptimizedDronePath(self):
        # Get the optimized route as a GeoDataFrame
        ordered_gdf = self.getOptimizedDronePath()
        
        if ordered_gdf is None or len(ordered_gdf) < 3:
            print("Could not generate optimized drone path.")
            return

        # Build PolyLine coordinates from the ordered GDF
        route_coords = []
        for _, row in ordered_gdf.iterrows():
            pt = row.geometry
            route_coords.append([pt.y, pt.x])
        
        # Connect back to start
        route_coords.append(route_coords[0])

        # CALL THE DISTANCE FUNCTION
        self.calculate_route_distance(ordered_gdf)
        self.print_route_legs(ordered_gdf)

        # Draw route line
        folium.PolyLine(
            locations=route_coords,
            color="green",
            weight=5,
            opacity=0.7,
            tooltip="Optimized Drone Route"
        ).add_to(self.map)
        
        # Mark waypoints with blue circles (excluding return-to-start)
        for i, coord in enumerate(route_coords[:-1]):
            folium.CircleMarker(
                location=coord,
                radius=5,
                color='#0000FF',
                fill=True,
                fill_color='#0000FF',
                fill_opacity=0.8,
                weight=2,
                popup=f"Waypoint {i+1}",
                tooltip=f"Stop {i+1}"
            ).add_to(self.map)
        
        print("TSP route with waypoints added successfully.")

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
