from kimDroneGoon.geo import geodata
from kimDroneGoon.visualize import visualizer

data = geodata(
    "kimDroneGoon\datasets\worldpopHK\hkg_ppp_2020_UNadj_constrained.tif",
    "kimDroneGoon\datasets\LUMHK_RasterGrid_2024\BLU.tif",
    "kimDroneGoon\datasets\sandboxZones\map.geojson"
)
visual = visualizer(data)
visual.addPopulationHeatmap(valTh=500)
visual.addOptimizedDronePath()
visual.addStrategicPeaks()
visual.render()
