from kimDroneGoon.geo import geodata
from kimDroneGoon.visualize import visualizer

# Load geographic data
data = geodata(
    "kimDroneGoon/datasets/worldpopHK/hkg_ppp_2020_UNadj_constrained.tif",
    "kimDroneGoon/datasets/LUMHK_RasterGrid_2024/BLU.tif",
    "kimDroneGoon/datasets/sandboxZones/map.geojson"
)

# Build and render visualization
viz = visualizer(data)
viz.addPopulationHeatmap(valTh=500)
viz.addOptimizedDronePath()
viz.addStrategicPeaks()
viz.render()
