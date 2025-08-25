# 安装必要包（如果尚未安装）
install.packages(c("raster", "sf", "RSAGA", "rgdal", "rgeos"))

# 加载包
library(raster)
library(sf)
library(RSAGA)
library(rgdal)
library(rgeos)

# 1. 设置工作环境和路径
work_dir <- "D:/"  # 替换为你的工作路径
setwd(work_dir)
dem_path <- "D:/ZJ.tif"   # DEM文件路径

# 2. 初始化SAGA环境
saga_env <- rsaga.env(
  path = "C:/Program Files/saga"  # 替换为你的SAGA安装路径
)

# 3. 水文分析预处理
# 3.1 填充洼地
rsaga.fill.sinks(
  in.dem = dem_path,
  out.dem = "filled_dem.sdat",
  method = "planchon.darboux.2001",
  env = saga_env
)

# 3.2 计算流向
rsaga.flow.direction(
  in.dem = "filled_dem.sdat",
  out.dir = "flow_direction.sdat",
  env = saga_env
)

# 3.3 计算汇流累积量
rsaga.flow.accumulation(
  in.dir = "flow_direction.sdat",
  out.acc = "flow_accumulation.sdat",
  env = saga_env
)

# 4. 提取流域边界
# 4.1 方法A：基于整个DEM提取流域网络
rsaga.watershed.delineation(
  in.dem = "filled_dem.sdat",
  in.dir = "flow_direction.sdat",
  out.basins = "watershed_basins.sdat",
  out.streams = "stream_network.sdat",
  min.size = 10000,  # 最小流域大小（像元数）
  env = saga_env
)

# 4.2 方法B：在指定出口点提取单个流域
# 定义出口点坐标（替换为你的实际坐标）
pour_point <- data.frame(
  x = 456789.0,  # 东坐标
  y = 5678901.0  # 北坐标
)

# 保存为点shapefile
st_write(
  st_as_sf(pour_point, coords = c("x", "y"), crs = st_crs(raster(dem_path))),
  "pour_point.shp",
  delete_layer = TRUE
)

# 转换为SAGA格式
rsaga.geoprocessor(
  "io_gdal", 0,
  list(
    FILES = "pour_point.shp",
    GRIDS = "pour_point.sgrd"
  ),
  env = saga_env
)

# 提取单个流域
rsaga.geoprocessor(
  "ta_hydrology", 3,  # 模块3: Watershed delineation
  list(
    DEM = "filled_dem.sdat",
    BASIN = "single_watershed.sdat",
    POINTS = "pour_point.sgrd"
  ),
  env = saga_env
)

# 5. 转换结果并保存为shp
# 5.1 读取流域栅格
watershed_raster <- raster("single_watershed.sdat")  # 或 "watershed_basins.sdat"

# 5.2 转换为多边形
watershed_poly <- rasterToPolygons(
  watershed_raster, 
  dissolve = TRUE,   # 溶解相邻多边形
  fun = function(x) x == maxValue(watershed_raster)  # 仅保留流域区域
) %>% 
  st_as_sf() %>%
  st_cast("MULTIPOLYGON")

# 5.3 简化几何（可选）
watershed_simple <- st_simplify(watershed_poly, dTolerance = 30)  # 容差单位与CRS一致

# 5.4 添加属性信息
watershed_simple$area_km2 <- as.numeric(st_area(watershed_simple)) / 1e6
watershed_simple$name <- "watershed"

# 5.5 保存为shapefile
st_write(
  watershed_simple, 
  "watershed_boundary.shp", 
  delete_layer = TRUE,  # 覆盖已存在文件
  delete_dsn = TRUE
)

# 6. 可视化结果
plot(watershed_simple["area_km2"], main = "流域边界", pal = terrain.colors)