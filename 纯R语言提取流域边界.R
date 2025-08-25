# 安装必要包（如果尚未安装）
install.packages(c("terra", "sf", "igraph", "rgeos", "lwgeom"))

# 加载包
library(terra)
library(sf)
library(igraph)
library(rgeos)
library(lwgeom)

# 1. 读取DEM数据
dem <- rast("path/to/your_dem.tif")  # 替换为你的DEM路径

# 2. 数据预处理
# 2.1 裁剪研究区域（可选，减少计算量）
# bbox <- c(xmin = , xmax = , ymin = , ymax = )  # 设置边界框
# dem <- crop(dem, bbox)

# 2.2 简化DEM（加速处理）
dem <- aggregate(dem, fact = 2)  # 降低分辨率

# 3. 洼地填充（简单方法）
fill_depressions <- function(dem) {
  # 创建填充后的DEM副本
  filled <- dem
  
  # 获取DEM值矩阵
  dem_mat <- as.matrix(dem, wide = TRUE)
  
  # 迭代填充过程
  for (iter in 1:5) {  # 控制迭代次数
    for (i in 2:(nrow(dem_mat)-1) {
      for (j in 2:(ncol(dem_mat)-1)) {
        # 跳过NA值
        if (is.na(dem_mat[i, j])) next
        
        # 获取3x3邻域
        neighbors <- dem_mat[(i-1):(i+1), (j-1):(j+1)]
        min_neighbor <- min(neighbors, na.rm = TRUE)
        
        # 如果中心点低于最低邻域点，则填充
        if (dem_mat[i, j] < min_neighbor) {
          filled[i-1, j-1] <- min_neighbor  # 调整索引以匹配terra对象
        }
      }
    }
    dem_mat <- as.matrix(filled, wide = TRUE)  # 更新矩阵
  }
  return(filled)
}

filled_dem <- fill_depressions(dem)

# 4. 计算水流方向（D8算法）
calculate_flow_direction <- function(dem) {
  # 初始化流向栅格（使用D8编码）
  flow_dir <- dem * 0
  dir_codes <- matrix(c(32, 64, 128, 16, 0, 1, 8, 4, 2), nrow = 3, byrow = TRUE)
  
  # 获取DEM矩阵
  dem_mat <- as.matrix(dem, wide = TRUE)
  
  # 计算每个像元的流向
  for (i in 2:(nrow(dem_mat)-1)) {
    for (j in 2:(ncol(dem_mat)-1)) {
      if (is.na(dem_mat[i, j])) next
      
      # 获取3x3邻域
      window <- dem_mat[(i-1):(i+1), (j-1):(j+1)]
      center <- window[2, 2]
      
      # 计算坡度
      slopes <- (center - window) / c(sqrt(2), 1, sqrt(2), 1, 0, 1, sqrt(2), 1, sqrt(2))
      slopes[5] <- -Inf  # 忽略中心点
      
      # 确定最大坡度方向
      max_slope <- max(slopes, na.rm = TRUE)
      
      # 仅考虑正坡度（水流向下）
      if (max_slope > 0) {
        max_idx <- which.max(slopes)
        flow_dir[i-1, j-1] <- dir_codes[max_idx]  # 调整索引
      } else {
        flow_dir[i-1, j-1] <- 0  # 平坦区域
      }
    }
  }
  return(flow_dir)
}

flow_dir <- calculate_flow_direction(filled_dem)

# 5. 计算汇流累积量
calculate_flow_accumulation <- function(flow_dir) {
  # 创建汇流累积量栅格
  flow_acc <- flow_dir * 0 + 1  # 初始值为1（每个像元贡献自身）
  
  # 创建流向图
  dir_matrix <- as.matrix(flow_dir, wide = TRUE)
  nrows <- nrow(dir_matrix)
  ncols <- ncol(dir_matrix)
  total_cells <- nrows * ncols
  
  # 创建邻接矩阵
  adj_matrix <- matrix(0, nrow = total_cells, ncol = total_cells)
  
  # 映射方向编码到行列偏移
  dir_map <- list(
    "32" = c(-1, -1), "64" = c(0, -1), "128" = c(1, -1),
    "16" = c(-1, 0), "0" = c(0, 0), "1" = c(1, 0),
    "8" = c(-1, 1), "4" = c(0, 1), "2" = c(1, 1)
  )
  
  # 构建流向图
  for (i in 1:nrows) {
    for (j in 1:ncols) {
      if (dir_matrix[i, j] == 0 || is.na(dir_matrix[i, j])) next
      
      # 当前像元索引
      cell_idx <- (j - 1) * nrows + i
      
      # 获取流向偏移
      dir_key <- as.character(dir_matrix[i, j])
      offset <- dir_map[[dir_key]]
      
      # 计算下游像元位置
      ni <- i + offset[1]
      nj <- j + offset[2]
      
      # 检查边界
      if (ni >= 1 && ni <= nrows && nj >= 1 && nj <= ncols) {
        # 下游像元索引
        down_idx <- (nj - 1) * nrows + ni
        adj_matrix[cell_idx, down_idx] <- 1
      }
    }
  }
  
  # 创建图对象
  g <- graph_from_adjacency_matrix(adj_matrix, mode = "directed")
  
  # 计算拓扑排序（从高到低）
  topo_order <- topo_sort(g, mode = "out")
  
  # 按拓扑顺序计算累积量
  for (cell in topo_order) {
    # 获取上游像元
    upstream <- neighbors(g, cell, mode = "in")
    
    # 累加上游贡献
    if (length(upstream) > 0) {
      flow_acc[cell] <- flow_acc[cell] + sum(flow_acc[upstream])
    }
  }
  
  # 转换为栅格
  flow_acc_rast <- rast(matrix(flow_acc, nrow = nrows, ncol = ncols), 
                        extent = ext(flow_dir), crs = crs(flow_dir))
  return(flow_acc_rast)
}

flow_acc <- calculate_flow_accumulation(flow_dir)

# 6. 提取流域边界
delineate_watershed <- function(flow_dir, pour_point) {
  # 获取行列号
  pp_row <- rowFromY(flow_dir, pour_point$y)
  pp_col <- colFromX(flow_dir, pour_point$x)
  
  # 初始化流域栅格
  watershed <- flow_dir * 0
  watershed[pp_row, pp_col] <- 1  # 标记出口点
  
  # 创建队列进行广度优先搜索
  queue <- list(list(row = pp_row, col = pp_col))
  
  # 方向偏移映射（反向追踪）
  reverse_dir_map <- list(
    "32" = c(1, 1),   "64" = c(0, 1),   "128" = c(-1, 1),
    "16" = c(1, 0),   "0" = c(0, 0),    "1" = c(-1, 0),
    "8" = c(1, -1),   "4" = c(0, -1),   "2" = c(-1, -1)
  )
  
  # 广度优先搜索（反向追踪上游）
  while (length(queue) > 0) {
    current <- queue[[1]]
    queue <- queue[-1]
    
    # 检查8个方向的上游像元
    for (dir_code in names(reverse_dir_map)) {
      offset <- reverse_dir_map[[dir_code]]
      new_row <- current$row + offset[1]
      new_col <- current$col + offset[2]
      
      # 检查边界
      if (new_row < 1 || new_row > nrow(flow_dir) || 
          new_col < 1 || new_col > ncol(flow_dir)) next
      
      # 检查是否已处理
      if (watershed[new_row, new_col] == 1) next
      
      # 获取当前像元的流向
      current_dir <- flow_dir[new_row, new_col]
      if (is.na(current_dir)) next
      
      # 检查流向是否指向当前像元（反向）
      target_row <- new_row + reverse_dir_map[[as.character(current_dir)]][1]
      target_col <- new_col + reverse_dir_map[[as.character(current_dir)]][2]
      
      if (target_row == current$row && target_col == current$col) {
        watershed[new_row, new_col] <- 1
        queue <- c(queue, list(list(row = new_row, col = new_col)))
      }
    }
  }
  
  return(watershed)
}

# 7. 设置出口点（手动或自动）
# 自动选择：DEM最低点
min_point <- xyFromCell(filled_dem, which.min(values(filled_dem)))
pour_point <- list(x = min_point[1, 1], y = min_point[1, 2])

# 手动设置出口点（取消注释并替换坐标）
# pour_point <- list(x = 经度, y = 纬度)

# 8. 提取流域
watershed_rast <- delineate_watershed(flow_dir, pour_point)

# 9. 转换为矢量边界
watershed_vec <- as.polygons(watershed_rast, dissolve = TRUE) %>% 
  st_as_sf() %>%
  st_cast("MULTIPOLYGON") %>%
  st_make_valid()

# 10. 简化边界
watershed_simple <- st_simplify(watershed_vec, dTolerance = 30)

# 11. 添加属性
watershed_simple$area_km2 <- as.numeric(st_area(watershed_simple)) / 1e6
watershed_simple$name <- "watershed"

# 12. 保存为Shapefile
st_write(watershed_simple, "watershed_boundary.shp", delete_dsn = TRUE)

# 13. 可视化结果
plot(flow_acc, col = terrain.colors(100), main = "汇流累积量")
plot(st_geometry(watershed_simple), add = TRUE, border = "red", lwd = 2)
points(pour_point$x, pour_point$y, pch = 17, col = "blue", cex = 2)