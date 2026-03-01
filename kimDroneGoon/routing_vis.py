import folium
from ortools.constraint_solver import routing_enums_pb2, pywrapcp

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
