# 加载必要的包
library(sf)          # 空间数据处理
library(raster)      # 栅格操作
library(dplyr)       # 数据操作
library(tidyr)       # 数据整理
library(lubridate)   # 日期处理
library(gstat)       # 空间插值
library(ggplot2)     # 绘图

# ----------------------
# 1. 数据准备与预处理
# ----------------------
# 读取湿地边界SHP
wetland_boundary <- st_read("wetland_design_boundary.shp") %>%
  st_transform(32650)  # 转换为UTM投影（根据实际位置调整）

# 读取污染物数据（COD, TN, TP, NH4-N）
pollutant_data <- read.csv("pollutant_concentrations.csv") %>%
  mutate(Date = as.Date(Date))  # 日期列转换

# 读取水量数据
flow_data <- read.csv("water_flow.csv") %>%
  mutate(Date = as.Date(Date))

# 读取基质参数
substrate_params <- read.csv("substrate_parameters.csv")

# 读取布水参数
water_dist_params <- read.csv("water_distribution_params.csv")

# 合并数据
analysis_data <- left_join(flow_data, pollutant_data, by = "Date") %>%
  drop_na()  # 删除缺失值

# ----------------------
# 2. 污染负荷计算
# ----------------------
# 计算公式：负荷(kg/d) = 浓度(mg/L) * 流量(m³/d) / 1000
loads <- analysis_data %>%
  mutate(
    COD_load = COD * Flow / 1000,
    TN_load = TN * Flow / 1000,
    TP_load = TP * Flow / 1000,
    NH4_load = NH4 * Flow / 1000
  ) %>%
  select(Date, contains("_load"))

# 保存污染负荷结果
write.csv(loads, "pollutant_loads.csv", row.names = FALSE)

# ----------------------
# 3. 水力负荷计算
# ----------------------
# 计算湿地面积（m²）
wetland_area <- st_area(wetland_boundary) %>% as.numeric()

# 计算日水力负荷 (m³/m²/d)
hydraulic_load <- analysis_data %>%
  mutate(HLR = Flow / wetland_area) %>%
  select(Date, HLR)

# 保存水力负荷结果
write.csv(hydraulic_load, "hydraulic_loading_rate.csv", row.names = FALSE)

# ----------------------
# 4. 堵塞热点分析
# ----------------------
# 4.1 空间插值准备
# 生成湿地范围内的规则网格
grid <- st_make_grid(wetland_boundary, cellsize = 1) %>%  # 1m分辨率网格
  st_as_sf() %>%
  st_intersection(wetland_boundary) %>%
  mutate(CellID = row_number())

# 4.2 整合空间参数（示例：使用基质厚度作为关键参数）
# 合并基质参数到网格（假设有"Location"字段关联位置）
substrate_grid <- left_join(grid, substrate_params, by = "Location")

# 4.3 堵塞风险模型（简化版）
# 风险指数 = 污染负荷 × 基质密度 / 渗透系数
risk_grid <- substrate_grid %>%
  mutate(
    Clog_Risk = (mean(loads$COD_load, na.rm = TRUE) * Density) / Hydraulic_Conductivity
  )

# 4.4 转换为栅格并输出TIFF
clog_raster <- rasterize(
  as_Spatial(risk_grid), 
  raster(extent(risk_grid), res = 1), 
  field = "Clog_Risk"
)
writeRaster(clog_raster, "clogging_hotspots.tiff", format = "GTiff")

# ----------------------
# 5. 结果可视化（示例）
# ----------------------
# 污染负荷时间序列
ggplot(loads, aes(x = Date)) +
  geom_line(aes(y = COD_load, color = "COD")) +
  geom_line(aes(y = TN_load, color = "TN")) +
  labs(title = "污染物负荷时间序列", y = "负荷 (kg/d)")

# 堵塞热点空间分布
ggplot(risk_grid) +
  geom_sf(aes(fill = Clog_Risk), color = NA) +
  scale_fill_viridis_c(option = "plasma", name = "堵塞风险指数") +
  labs(title = "潜流湿地堵塞风险分布")