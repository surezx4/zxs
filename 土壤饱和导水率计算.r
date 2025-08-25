# 饱和导水率计算函数（基于Campbell模型）
calculate_ksat <- function(bd, sand, silt, clay) {
  # 检查质地总和是否接近100%
  total_texture <- sand + silt + clay
  if (abs(total_texture - 100) > 1) {
    warning(paste("质地总和为", total_texture, "%，不是100%。结果可能不准确。"))
  }
  
  # 计算孔隙度（饱和含水量）
  particle_density <- 2.65  # 土壤颗粒密度 (g/cm³)
  theta_s <- 1 - (bd / particle_density)
  
  # 计算质地参数 B (基于Cosby et al. 1984)
  B <- 2.91 + 0.159 * clay  # 粘粒主导的公式
  
  # 模型参数
  K0 <- 1.16e-2    # 参考导水率 (cm/s)
  theta0 <- 0.45   # 参考孔隙率
  
  # 计算饱和导水率 (cm/s)
  ksat_cm_s <- K0 * (theta_s / theta0)^(2*B + 3)
  
  # 转换为常用单位 cm/day
  ksat_cm_day <- ksat_cm_s * 86400
  
  # 返回结果列表
  return(list(
    porosity = theta_s,
    B_parameter = B,
    ksat_cm_s = ksat_cm_s,
    ksat_cm_day = ksat_cm_day
  ))
}

# 主程序
# 安装必要包（如果未安装）
if (!require("dplyr")) install.packages("dplyr")
library(dplyr)

# 设置工作目录（替换为你的CSV文件路径）
setwd("D:/")

# 读取CSV文件（假设文件名为soil_data.csv）
tryCatch({
  soil_data <- read.csv("SOIL.csv", stringsAsFactors = FALSE)
  
  # 检查必要的列是否存在
  required_cols <- c("BD", "Sand", "Silt", "Clay")
  if (!all(required_cols %in% colnames(soil_data))) {
    missing_cols <- setdiff(required_cols, colnames(soil_data))
    stop(paste("CSV文件中缺少必要的列:", paste(missing_cols, collapse = ", ")))
  }
  
  # 应用计算函数到每一行
  results <- lapply(1:nrow(soil_data), function(i) {
    row <- soil_data[i, ]
    calc <- calculate_ksat(
      bd = row$BD,
      sand = row$Sand,
      silt = row$Silt,
      clay = row$Clay
    )
    return(calc)
  })
  
  # 提取结果并添加到数据框
  soil_data$Porosity <- sapply(results, function(x) x$porosity)
  soil_data$B_Parameter <- sapply(results, function(x) x$B_parameter)
  soil_data$Ksat_cm_s <- sapply(results, function(x) x$ksat_cm_s)
  soil_data$Ksat_cm_day <- sapply(results, function(x) x$ksat_cm_day)
  
  # 导出结果到新CSV文件
  output_file <- "D:/soil_ksat_results.csv"
  write.csv(soil_data, output_file, row.names = FALSE)
  
  # 打印成功消息
  message(paste("计算完成！结果已保存到:", output_file))
  message(paste("处理了", nrow(soil_data), "行数据"))
  message("输出文件包含以下列:")
  message(paste(colnames(soil_data), collapse = ", "))
  
}, error = function(e) {
  message("发生错误: ", e$message)
  message("请确保:")
  message("1. 文件'soil_data.csv'存在于工作目录")
  message("2. 文件包含BD(容重), Sand(砂粒%), Silt(粉粒%), Clay(粘粒%)列")
  message("3. 所有值都是数值型且无缺失值")
})