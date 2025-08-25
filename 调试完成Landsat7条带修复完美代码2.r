# ======================================================
# Landsat条带修复工具 - 自动尺寸调整版
# 版本: 4.1 (语法修正版)
# 作者: 地理空间分析专家
# 日期: 2023-11-15
# ======================================================

# 加载必要的库
library(raster)
library(zoo)
library(tools)

# ----------------------
# 用户配置区域
# ----------------------

# 设置工作目录
setwd("D:/LE0705")

# 定义原始波段文件
band_files <- c("B1.tif", "B2.tif", "B3.tif", "B4.tif", "B5.tif", "B7.tif")

# 定义参照波段前缀
ref_prefix <- "Ref_"

# 创建输出目录
output_dir <- "Repaired_Output"
if (!dir.exists(output_dir)) {
  dir.create(output_dir)
}

# 创建日志文件
log_file <- file.path(output_dir, "repair_log.txt")
sink(log_file, split = TRUE)  # 同时输出到控制台和日志文件

# ----------------------
# 日志记录函数
# ----------------------

log_message <- function(message) {
  timestamp <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  cat(paste0("[", timestamp, "] ", message, "\n"))
}

# ----------------------
# 尺寸调整函数
# ----------------------

adjust_raster_size <- function(main_raster, ref_raster) {
  # 检查尺寸是否匹配
  if (all(dim(main_raster) == dim(ref_raster))) {
    return(main_raster)
  }
  
  log_message(paste("尺寸不匹配: 原始", dim(main_raster), "参照", dim(ref_raster)))
  log_message("正在进行尺寸调整...")
  
  # 创建目标栅格模板
  target_template <- ref_raster
  
  # 重采样主栅格以匹配参照栅格
  resampled_raster <- resample(main_raster, target_template, method = "bilinear")
  
  log_message(paste("调整后尺寸:", dim(resampled_raster)))
  
  return(resampled_raster)
}

# ----------------------
# 文件检查与加载
# ----------------------

log_message("======= 开始Landsat条带修复 =======")
log_message(paste("工作目录:", getwd()))
log_message(paste("输出目录:", output_dir))

# 检查文件存在性
check_files <- function(files) {
  missing_files <- character(0)
  
  for (f in files) {
    if (!file.exists(f)) {
      missing_files <- c(missing_files, f)
    }
  }
  
  if (length(missing_files) > 0) {
    log_message("错误: 以下文件缺失:")
    for (f in missing_files) {
      log_message(paste(" -", f))
    }
    return(FALSE)
  }
  return(TRUE)
}

# 生成参照波段文件列表
ref_band_files <- paste0(ref_prefix, band_files)

# 验证所有文件
all_files <- c(band_files, ref_band_files)
if (!check_files(all_files)) {
  stop("文件缺失，请检查工作目录")
} else {
  log_message("所有文件存在性验证通过")
}

# ----------------------
# 核心修复函数 (带尺寸调整)
# ----------------------

repair_band_with_adjustment <- function(input_file, ref_file) {
  start_time <- Sys.time()
  log_message(paste(">>> 开始处理波段:", basename(input_file)))
  log_message(paste("参照波段:", basename(ref_file)))
  
  tryCatch({
    # 读取栅格数据
    band_ras <- raster(input_file)
    ref_ras <- raster(ref_file)
    
    # 记录原始尺寸
    original_dim <- dim(band_ras)
    
    # 调整尺寸以匹配参照波段
    band_ras <- adjust_raster_size(band_ras, ref_ras)
    
    # 记录栅格信息
    log_message(paste("调整后尺寸:", dim(band_ras)))
    log_message(paste("参照波段尺寸:", dim(ref_ras)))
    log_message(paste("原始数据类型:", dataType(band_ras)))
    
    # 创建输出栅格
    output_ras <- raster(band_ras)
    
    # 将0值设为NA（表示缺失）
    band_ras[band_ras == 0] <- NA
    
    # 转换为矩阵
    band_mat <- as.matrix(band_ras)
    ref_mat <- as.matrix(ref_ras)
    
    # 获取缺失掩膜
    na_mask <- is.na(band_mat)
    na_count <- sum(na_mask)
    total_pixels <- length(band_mat)
    
    if (na_count == 0) {
      log_message("没有缺失值，跳过修复")
      return(band_ras)
    }
    
    log_message(paste("缺失像素:", na_count, "(", round(100 * na_count/total_pixels, 2), "%)"))
    
    # 步骤1: 垂直插值
    log_message("步骤1: 垂直插值...")
    band_mat <- apply(band_mat, 2, function(col) {
      na.approx(col, na.rm = FALSE, rule = 2, maxgap = 10)
    })
    
    # 步骤2: 水平插值 (修复语法错误)
    log_message("步骤2: 水平插值...")
    band_mat <- t(apply(band_mat, 1, function(row) {
      na.approx(row, na.rm = FALSE, rule = 2, maxgap = 10)
    }))  # 修复：添加了缺失的括号
    
    # 步骤3: 修复剩余缺失值
    remaining_na <- sum(is.na(band_mat))
    if (remaining_na > 0) {
      log_message(paste("步骤3: 修复剩余缺失值 (", remaining_na, "像素)"))
      
      # 使用参照值填充剩余缺失
      band_mat[is.na(band_mat)] <- ref_mat[is.na(band_mat)]
    }
    
    # 创建修复后的栅格
    values(output_ras) <- as.vector(t(band_mat))
    
    # 保持原始数据类型
    original_dtype <- dataType(band_ras)
    if (original_dtype %in% c("INT2U", "INT2S")) {
      vals <- getValues(output_ras)
      if (original_dtype == "INT2U") {
        vals <- round(pmin(pmax(vals, 0), 65535))
      } else {
        vals <- round(pmin(pmax(vals, -32768), 32767))
      }
      output_ras <- setValues(output_ras, vals)
      dataType(output_ras) <- original_dtype
    }
    
    # 计算处理时间
    time_taken <- round(as.numeric(difftime(Sys.time(), start_time, units = "secs")), 1)
    log_message(paste("<<< 处理成功! 耗时:", time_taken, "秒"))
    
    return(output_ras)
  }, error = function(e) {
    log_message(paste("处理失败:", e$message))
    return(NULL)
  })
}

# ----------------------
# 主处理流程
# ----------------------

# 初始化修复后的波段列表
repaired_bands <- list()
success_count <- 0

log_message(paste("处理波段数量:", length(band_files)))

# 逐个处理波段
for (i in seq_along(band_files)) {
  band <- band_files[i]
  ref_band <- ref_band_files[i]
  
  log_message(paste("\n--- 处理波段", i, "/", length(band_files), ":", band, "---"))
  
  # 修复波段
  repaired <- repair_band_with_adjustment(band, ref_band)
  
  if (!is.null(repaired)) {
    # 保存到列表
    repaired_bands[[length(repaired_bands) + 1]] <- repaired
    success_count <- success_count + 1
    
    # 保存单波段文件
    output_name <- paste0("repaired_", tools::file_path_sans_ext(band), ".tif")
    output_path <- file.path(output_dir, output_name)
    
    writeRaster(
      repaired,
      output_path,
      format = "GTiff",
      datatype = dataType(repaired),
      overwrite = TRUE,
      options = c("COMPRESS=LZW", "BIGTIFF=IF_SAFER")
    )
    
    log_message(paste("已保存:", output_path))
  }
  
  # 清理内存
  gc()
}

# ----------------------
# 创建多波段合成图像
# ----------------------

if (success_count > 0) {
  log_message("\n创建多波段合成图像...")
  
  # 创建堆栈
  band_stack <- stack(repaired_bands)
  
  # 设置波段名称
  band_names <- c("Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2")[1:length(repaired_bands)]
  names(band_stack) <- band_names
  
  # 保存合成图像
  composite_path <- file.path(output_dir, "landsat_composite.tif")
  writeRaster(
    band_stack,
    composite_path,
    format = "GTiff",
    datatype = dataType(repaired_bands[[1]]),
    overwrite = TRUE,
    options = c("COMPRESS=LZW", "BIGTIFF=IF_SAFER")
  )
  
  log_message(paste("合成图像已保存:", composite_path))
  
  # 生成预览图
  log_message("\n生成预览图...")
  preview_path <- file.path(output_dir, "landsat_preview.png")
  png(preview_path, width = 1000, height = 800)
  
  if (nlayers(band_stack) >= 3) {
    plotRGB(band_stack, r = 3, g = 2, b = 1, stretch = "lin", 
            main = "修复后的Landsat图像")
  } else if (nlayers(band_stack) > 0) {
    plot(band_stack[[1]], main = "修复后的Landsat波段")
  }
  
  dev.off()
  log_message(paste("预览图已保存:", preview_path))
} else {
  log_message("\n警告: 没有成功修复的波段")
}

# ----------------------
# 完成报告
# ----------------------

log_message("\n======= 处理完成! =======")
log_message(paste("成功修复波段:", success_count, "/", length(band_files)))
log_message(paste("输出文件位置:", output_dir))
log_message(paste("日志文件:", log_file))

# 关闭日志
sink()













# 设置工作目录
setwd("D:/LE0706")

# 定义原始波段文件
band_files <- c("B1.tif", "B2.tif", "B3.tif", "B4.tif", "B5.tif", "B7.tif")

# 定义参照波段前缀
ref_prefix <- "Ref_"

# 创建输出目录
output_dir <- "Repaired_Output"
if (!dir.exists(output_dir)) {
  dir.create(output_dir)
}

# 创建日志文件
log_file <- file.path(output_dir, "repair_log.txt")
sink(log_file, split = TRUE)  # 同时输出到控制台和日志文件

# ----------------------
# 日志记录函数
# ----------------------

log_message <- function(message) {
  timestamp <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  cat(paste0("[", timestamp, "] ", message, "\n"))
}

# ----------------------
# 尺寸调整函数
# ----------------------

adjust_raster_size <- function(main_raster, ref_raster) {
  # 检查尺寸是否匹配
  if (all(dim(main_raster) == dim(ref_raster))) {
    return(main_raster)
  }
  
  log_message(paste("尺寸不匹配: 原始", dim(main_raster), "参照", dim(ref_raster)))
  log_message("正在进行尺寸调整...")
  
  # 创建目标栅格模板
  target_template <- ref_raster
  
  # 重采样主栅格以匹配参照栅格
  resampled_raster <- resample(main_raster, target_template, method = "bilinear")
  
  log_message(paste("调整后尺寸:", dim(resampled_raster)))
  
  return(resampled_raster)
}

# ----------------------
# 文件检查与加载
# ----------------------

log_message("======= 开始Landsat条带修复 =======")
log_message(paste("工作目录:", getwd()))
log_message(paste("输出目录:", output_dir))

# 检查文件存在性
check_files <- function(files) {
  missing_files <- character(0)
  
  for (f in files) {
    if (!file.exists(f)) {
      missing_files <- c(missing_files, f)
    }
  }
  
  if (length(missing_files) > 0) {
    log_message("错误: 以下文件缺失:")
    for (f in missing_files) {
      log_message(paste(" -", f))
    }
    return(FALSE)
  }
  return(TRUE)
}

# 生成参照波段文件列表
ref_band_files <- paste0(ref_prefix, band_files)

# 验证所有文件
all_files <- c(band_files, ref_band_files)
if (!check_files(all_files)) {
  stop("文件缺失，请检查工作目录")
} else {
  log_message("所有文件存在性验证通过")
}

# ----------------------
# 核心修复函数 (带尺寸调整)
# ----------------------

repair_band_with_adjustment <- function(input_file, ref_file) {
  start_time <- Sys.time()
  log_message(paste(">>> 开始处理波段:", basename(input_file)))
  log_message(paste("参照波段:", basename(ref_file)))
  
  tryCatch({
    # 读取栅格数据
    band_ras <- raster(input_file)
    ref_ras <- raster(ref_file)
    
    # 记录原始尺寸
    original_dim <- dim(band_ras)
    
    # 调整尺寸以匹配参照波段
    band_ras <- adjust_raster_size(band_ras, ref_ras)
    
    # 记录栅格信息
    log_message(paste("调整后尺寸:", dim(band_ras)))
    log_message(paste("参照波段尺寸:", dim(ref_ras)))
    log_message(paste("原始数据类型:", dataType(band_ras)))
    
    # 创建输出栅格
    output_ras <- raster(band_ras)
    
    # 将0值设为NA（表示缺失）
    band_ras[band_ras == 0] <- NA
    
    # 转换为矩阵
    band_mat <- as.matrix(band_ras)
    ref_mat <- as.matrix(ref_ras)
    
    # 获取缺失掩膜
    na_mask <- is.na(band_mat)
    na_count <- sum(na_mask)
    total_pixels <- length(band_mat)
    
    if (na_count == 0) {
      log_message("没有缺失值，跳过修复")
      return(band_ras)
    }
    
    log_message(paste("缺失像素:", na_count, "(", round(100 * na_count/total_pixels, 2), "%)"))
    
    # 步骤1: 垂直插值
    log_message("步骤1: 垂直插值...")
    band_mat <- apply(band_mat, 2, function(col) {
      na.approx(col, na.rm = FALSE, rule = 2, maxgap = 10)
    })
    
    # 步骤2: 水平插值 (修复语法错误)
    log_message("步骤2: 水平插值...")
    band_mat <- t(apply(band_mat, 1, function(row) {
      na.approx(row, na.rm = FALSE, rule = 2, maxgap = 10)
    }))  # 修复：添加了缺失的括号
    
    # 步骤3: 修复剩余缺失值
    remaining_na <- sum(is.na(band_mat))
    if (remaining_na > 0) {
      log_message(paste("步骤3: 修复剩余缺失值 (", remaining_na, "像素)"))
      
      # 使用参照值填充剩余缺失
      band_mat[is.na(band_mat)] <- ref_mat[is.na(band_mat)]
    }
    
    # 创建修复后的栅格
    values(output_ras) <- as.vector(t(band_mat))
    
    # 保持原始数据类型
    original_dtype <- dataType(band_ras)
    if (original_dtype %in% c("INT2U", "INT2S")) {
      vals <- getValues(output_ras)
      if (original_dtype == "INT2U") {
        vals <- round(pmin(pmax(vals, 0), 65535))
      } else {
        vals <- round(pmin(pmax(vals, -32768), 32767))
      }
      output_ras <- setValues(output_ras, vals)
      dataType(output_ras) <- original_dtype
    }
    
    # 计算处理时间
    time_taken <- round(as.numeric(difftime(Sys.time(), start_time, units = "secs")), 1)
    log_message(paste("<<< 处理成功! 耗时:", time_taken, "秒"))
    
    return(output_ras)
  }, error = function(e) {
    log_message(paste("处理失败:", e$message))
    return(NULL)
  })
}

# ----------------------
# 主处理流程
# ----------------------

# 初始化修复后的波段列表
repaired_bands <- list()
success_count <- 0

log_message(paste("处理波段数量:", length(band_files)))

# 逐个处理波段
for (i in seq_along(band_files)) {
  band <- band_files[i]
  ref_band <- ref_band_files[i]
  
  log_message(paste("\n--- 处理波段", i, "/", length(band_files), ":", band, "---"))
  
  # 修复波段
  repaired <- repair_band_with_adjustment(band, ref_band)
  
  if (!is.null(repaired)) {
    # 保存到列表
    repaired_bands[[length(repaired_bands) + 1]] <- repaired
    success_count <- success_count + 1
    
    # 保存单波段文件
    output_name <- paste0("repaired_", tools::file_path_sans_ext(band), ".tif")
    output_path <- file.path(output_dir, output_name)
    
    writeRaster(
      repaired,
      output_path,
      format = "GTiff",
      datatype = dataType(repaired),
      overwrite = TRUE,
      options = c("COMPRESS=LZW", "BIGTIFF=IF_SAFER")
    )
    
    log_message(paste("已保存:", output_path))
  }
  
  # 清理内存
  gc()
}

# ----------------------
# 创建多波段合成图像
# ----------------------

if (success_count > 0) {
  log_message("\n创建多波段合成图像...")
  
  # 创建堆栈
  band_stack <- stack(repaired_bands)
  
  # 设置波段名称
  band_names <- c("Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2")[1:length(repaired_bands)]
  names(band_stack) <- band_names
  
  # 保存合成图像
  composite_path <- file.path(output_dir, "landsat_composite.tif")
  writeRaster(
    band_stack,
    composite_path,
    format = "GTiff",
    datatype = dataType(repaired_bands[[1]]),
    overwrite = TRUE,
    options = c("COMPRESS=LZW", "BIGTIFF=IF_SAFER")
  )
  
  log_message(paste("合成图像已保存:", composite_path))
  
  # 生成预览图
  log_message("\n生成预览图...")
  preview_path <- file.path(output_dir, "landsat_preview.png")
  png(preview_path, width = 1000, height = 800)
  
  if (nlayers(band_stack) >= 3) {
    plotRGB(band_stack, r = 3, g = 2, b = 1, stretch = "lin", 
            main = "修复后的Landsat图像")
  } else if (nlayers(band_stack) > 0) {
    plot(band_stack[[1]], main = "修复后的Landsat波段")
  }
  
  dev.off()
  log_message(paste("预览图已保存:", preview_path))
} else {
  log_message("\n警告: 没有成功修复的波段")
}

# ----------------------
# 完成报告
# ----------------------

log_message("\n======= 处理完成! =======")
log_message(paste("成功修复波段:", success_count, "/", length(band_files)))
log_message(paste("输出文件位置:", output_dir))
log_message(paste("日志文件:", log_file))

# 关闭日志
sink()











# 设置工作目录
setwd("D:/LE0707")

# 定义原始波段文件
band_files <- c("B1.tif", "B2.tif", "B3.tif", "B4.tif", "B5.tif", "B7.tif")

# 定义参照波段前缀
ref_prefix <- "Ref_"

# 创建输出目录
output_dir <- "Repaired_Output"
if (!dir.exists(output_dir)) {
  dir.create(output_dir)
}

# 创建日志文件
log_file <- file.path(output_dir, "repair_log.txt")
sink(log_file, split = TRUE)  # 同时输出到控制台和日志文件

# ----------------------
# 日志记录函数
# ----------------------

log_message <- function(message) {
  timestamp <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  cat(paste0("[", timestamp, "] ", message, "\n"))
}

# ----------------------
# 尺寸调整函数
# ----------------------

adjust_raster_size <- function(main_raster, ref_raster) {
  # 检查尺寸是否匹配
  if (all(dim(main_raster) == dim(ref_raster))) {
    return(main_raster)
  }
  
  log_message(paste("尺寸不匹配: 原始", dim(main_raster), "参照", dim(ref_raster)))
  log_message("正在进行尺寸调整...")
  
  # 创建目标栅格模板
  target_template <- ref_raster
  
  # 重采样主栅格以匹配参照栅格
  resampled_raster <- resample(main_raster, target_template, method = "bilinear")
  
  log_message(paste("调整后尺寸:", dim(resampled_raster)))
  
  return(resampled_raster)
}

# ----------------------
# 文件检查与加载
# ----------------------

log_message("======= 开始Landsat条带修复 =======")
log_message(paste("工作目录:", getwd()))
log_message(paste("输出目录:", output_dir))

# 检查文件存在性
check_files <- function(files) {
  missing_files <- character(0)
  
  for (f in files) {
    if (!file.exists(f)) {
      missing_files <- c(missing_files, f)
    }
  }
  
  if (length(missing_files) > 0) {
    log_message("错误: 以下文件缺失:")
    for (f in missing_files) {
      log_message(paste(" -", f))
    }
    return(FALSE)
  }
  return(TRUE)
}

# 生成参照波段文件列表
ref_band_files <- paste0(ref_prefix, band_files)

# 验证所有文件
all_files <- c(band_files, ref_band_files)
if (!check_files(all_files)) {
  stop("文件缺失，请检查工作目录")
} else {
  log_message("所有文件存在性验证通过")
}

# ----------------------
# 核心修复函数 (带尺寸调整)
# ----------------------

repair_band_with_adjustment <- function(input_file, ref_file) {
  start_time <- Sys.time()
  log_message(paste(">>> 开始处理波段:", basename(input_file)))
  log_message(paste("参照波段:", basename(ref_file)))
  
  tryCatch({
    # 读取栅格数据
    band_ras <- raster(input_file)
    ref_ras <- raster(ref_file)
    
    # 记录原始尺寸
    original_dim <- dim(band_ras)
    
    # 调整尺寸以匹配参照波段
    band_ras <- adjust_raster_size(band_ras, ref_ras)
    
    # 记录栅格信息
    log_message(paste("调整后尺寸:", dim(band_ras)))
    log_message(paste("参照波段尺寸:", dim(ref_ras)))
    log_message(paste("原始数据类型:", dataType(band_ras)))
    
    # 创建输出栅格
    output_ras <- raster(band_ras)
    
    # 将0值设为NA（表示缺失）
    band_ras[band_ras == 0] <- NA
    
    # 转换为矩阵
    band_mat <- as.matrix(band_ras)
    ref_mat <- as.matrix(ref_ras)
    
    # 获取缺失掩膜
    na_mask <- is.na(band_mat)
    na_count <- sum(na_mask)
    total_pixels <- length(band_mat)
    
    if (na_count == 0) {
      log_message("没有缺失值，跳过修复")
      return(band_ras)
    }
    
    log_message(paste("缺失像素:", na_count, "(", round(100 * na_count/total_pixels, 2), "%)"))
    
    # 步骤1: 垂直插值
    log_message("步骤1: 垂直插值...")
    band_mat <- apply(band_mat, 2, function(col) {
      na.approx(col, na.rm = FALSE, rule = 2, maxgap = 10)
    })
    
    # 步骤2: 水平插值 (修复语法错误)
    log_message("步骤2: 水平插值...")
    band_mat <- t(apply(band_mat, 1, function(row) {
      na.approx(row, na.rm = FALSE, rule = 2, maxgap = 10)
    }))  # 修复：添加了缺失的括号
    
    # 步骤3: 修复剩余缺失值
    remaining_na <- sum(is.na(band_mat))
    if (remaining_na > 0) {
      log_message(paste("步骤3: 修复剩余缺失值 (", remaining_na, "像素)"))
      
      # 使用参照值填充剩余缺失
      band_mat[is.na(band_mat)] <- ref_mat[is.na(band_mat)]
    }
    
    # 创建修复后的栅格
    values(output_ras) <- as.vector(t(band_mat))
    
    # 保持原始数据类型
    original_dtype <- dataType(band_ras)
    if (original_dtype %in% c("INT2U", "INT2S")) {
      vals <- getValues(output_ras)
      if (original_dtype == "INT2U") {
        vals <- round(pmin(pmax(vals, 0), 65535))
      } else {
        vals <- round(pmin(pmax(vals, -32768), 32767))
      }
      output_ras <- setValues(output_ras, vals)
      dataType(output_ras) <- original_dtype
    }
    
    # 计算处理时间
    time_taken <- round(as.numeric(difftime(Sys.time(), start_time, units = "secs")), 1)
    log_message(paste("<<< 处理成功! 耗时:", time_taken, "秒"))
    
    return(output_ras)
  }, error = function(e) {
    log_message(paste("处理失败:", e$message))
    return(NULL)
  })
}

# ----------------------
# 主处理流程
# ----------------------

# 初始化修复后的波段列表
repaired_bands <- list()
success_count <- 0

log_message(paste("处理波段数量:", length(band_files)))

# 逐个处理波段
for (i in seq_along(band_files)) {
  band <- band_files[i]
  ref_band <- ref_band_files[i]
  
  log_message(paste("\n--- 处理波段", i, "/", length(band_files), ":", band, "---"))
  
  # 修复波段
  repaired <- repair_band_with_adjustment(band, ref_band)
  
  if (!is.null(repaired)) {
    # 保存到列表
    repaired_bands[[length(repaired_bands) + 1]] <- repaired
    success_count <- success_count + 1
    
    # 保存单波段文件
    output_name <- paste0("repaired_", tools::file_path_sans_ext(band), ".tif")
    output_path <- file.path(output_dir, output_name)
    
    writeRaster(
      repaired,
      output_path,
      format = "GTiff",
      datatype = dataType(repaired),
      overwrite = TRUE,
      options = c("COMPRESS=LZW", "BIGTIFF=IF_SAFER")
    )
    
    log_message(paste("已保存:", output_path))
  }
  
  # 清理内存
  gc()
}

# ----------------------
# 创建多波段合成图像
# ----------------------

if (success_count > 0) {
  log_message("\n创建多波段合成图像...")
  
  # 创建堆栈
  band_stack <- stack(repaired_bands)
  
  # 设置波段名称
  band_names <- c("Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2")[1:length(repaired_bands)]
  names(band_stack) <- band_names
  
  # 保存合成图像
  composite_path <- file.path(output_dir, "landsat_composite.tif")
  writeRaster(
    band_stack,
    composite_path,
    format = "GTiff",
    datatype = dataType(repaired_bands[[1]]),
    overwrite = TRUE,
    options = c("COMPRESS=LZW", "BIGTIFF=IF_SAFER")
  )
  
  log_message(paste("合成图像已保存:", composite_path))
  
  # 生成预览图
  log_message("\n生成预览图...")
  preview_path <- file.path(output_dir, "landsat_preview.png")
  png(preview_path, width = 1000, height = 800)
  
  if (nlayers(band_stack) >= 3) {
    plotRGB(band_stack, r = 3, g = 2, b = 1, stretch = "lin", 
            main = "修复后的Landsat图像")
  } else if (nlayers(band_stack) > 0) {
    plot(band_stack[[1]], main = "修复后的Landsat波段")
  }
  
  dev.off()
  log_message(paste("预览图已保存:", preview_path))
} else {
  log_message("\n警告: 没有成功修复的波段")
}

# ----------------------
# 完成报告
# ----------------------

log_message("\n======= 处理完成! =======")
log_message(paste("成功修复波段:", success_count, "/", length(band_files)))
log_message(paste("输出文件位置:", output_dir))
log_message(paste("日志文件:", log_file))

# 关闭日志
sink()











# 设置工作目录
setwd("D:/LE0708")

# 定义原始波段文件
band_files <- c("B1.tif", "B2.tif", "B3.tif", "B4.tif", "B5.tif", "B7.tif")

# 定义参照波段前缀
ref_prefix <- "Ref_"

# 创建输出目录
output_dir <- "Repaired_Output"
if (!dir.exists(output_dir)) {
  dir.create(output_dir)
}

# 创建日志文件
log_file <- file.path(output_dir, "repair_log.txt")
sink(log_file, split = TRUE)  # 同时输出到控制台和日志文件

# ----------------------
# 日志记录函数
# ----------------------

log_message <- function(message) {
  timestamp <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  cat(paste0("[", timestamp, "] ", message, "\n"))
}

# ----------------------
# 尺寸调整函数
# ----------------------

adjust_raster_size <- function(main_raster, ref_raster) {
  # 检查尺寸是否匹配
  if (all(dim(main_raster) == dim(ref_raster))) {
    return(main_raster)
  }
  
  log_message(paste("尺寸不匹配: 原始", dim(main_raster), "参照", dim(ref_raster)))
  log_message("正在进行尺寸调整...")
  
  # 创建目标栅格模板
  target_template <- ref_raster
  
  # 重采样主栅格以匹配参照栅格
  resampled_raster <- resample(main_raster, target_template, method = "bilinear")
  
  log_message(paste("调整后尺寸:", dim(resampled_raster)))
  
  return(resampled_raster)
}

# ----------------------
# 文件检查与加载
# ----------------------

log_message("======= 开始Landsat条带修复 =======")
log_message(paste("工作目录:", getwd()))
log_message(paste("输出目录:", output_dir))

# 检查文件存在性
check_files <- function(files) {
  missing_files <- character(0)
  
  for (f in files) {
    if (!file.exists(f)) {
      missing_files <- c(missing_files, f)
    }
  }
  
  if (length(missing_files) > 0) {
    log_message("错误: 以下文件缺失:")
    for (f in missing_files) {
      log_message(paste(" -", f))
    }
    return(FALSE)
  }
  return(TRUE)
}

# 生成参照波段文件列表
ref_band_files <- paste0(ref_prefix, band_files)

# 验证所有文件
all_files <- c(band_files, ref_band_files)
if (!check_files(all_files)) {
  stop("文件缺失，请检查工作目录")
} else {
  log_message("所有文件存在性验证通过")
}

# ----------------------
# 核心修复函数 (带尺寸调整)
# ----------------------

repair_band_with_adjustment <- function(input_file, ref_file) {
  start_time <- Sys.time()
  log_message(paste(">>> 开始处理波段:", basename(input_file)))
  log_message(paste("参照波段:", basename(ref_file)))
  
  tryCatch({
    # 读取栅格数据
    band_ras <- raster(input_file)
    ref_ras <- raster(ref_file)
    
    # 记录原始尺寸
    original_dim <- dim(band_ras)
    
    # 调整尺寸以匹配参照波段
    band_ras <- adjust_raster_size(band_ras, ref_ras)
    
    # 记录栅格信息
    log_message(paste("调整后尺寸:", dim(band_ras)))
    log_message(paste("参照波段尺寸:", dim(ref_ras)))
    log_message(paste("原始数据类型:", dataType(band_ras)))
    
    # 创建输出栅格
    output_ras <- raster(band_ras)
    
    # 将0值设为NA（表示缺失）
    band_ras[band_ras == 0] <- NA
    
    # 转换为矩阵
    band_mat <- as.matrix(band_ras)
    ref_mat <- as.matrix(ref_ras)
    
    # 获取缺失掩膜
    na_mask <- is.na(band_mat)
    na_count <- sum(na_mask)
    total_pixels <- length(band_mat)
    
    if (na_count == 0) {
      log_message("没有缺失值，跳过修复")
      return(band_ras)
    }
    
    log_message(paste("缺失像素:", na_count, "(", round(100 * na_count/total_pixels, 2), "%)"))
    
    # 步骤1: 垂直插值
    log_message("步骤1: 垂直插值...")
    band_mat <- apply(band_mat, 2, function(col) {
      na.approx(col, na.rm = FALSE, rule = 2, maxgap = 10)
    })
    
    # 步骤2: 水平插值 (修复语法错误)
    log_message("步骤2: 水平插值...")
    band_mat <- t(apply(band_mat, 1, function(row) {
      na.approx(row, na.rm = FALSE, rule = 2, maxgap = 10)
    }))  # 修复：添加了缺失的括号
    
    # 步骤3: 修复剩余缺失值
    remaining_na <- sum(is.na(band_mat))
    if (remaining_na > 0) {
      log_message(paste("步骤3: 修复剩余缺失值 (", remaining_na, "像素)"))
      
      # 使用参照值填充剩余缺失
      band_mat[is.na(band_mat)] <- ref_mat[is.na(band_mat)]
    }
    
    # 创建修复后的栅格
    values(output_ras) <- as.vector(t(band_mat))
    
    # 保持原始数据类型
    original_dtype <- dataType(band_ras)
    if (original_dtype %in% c("INT2U", "INT2S")) {
      vals <- getValues(output_ras)
      if (original_dtype == "INT2U") {
        vals <- round(pmin(pmax(vals, 0), 65535))
      } else {
        vals <- round(pmin(pmax(vals, -32768), 32767))
      }
      output_ras <- setValues(output_ras, vals)
      dataType(output_ras) <- original_dtype
    }
    
    # 计算处理时间
    time_taken <- round(as.numeric(difftime(Sys.time(), start_time, units = "secs")), 1)
    log_message(paste("<<< 处理成功! 耗时:", time_taken, "秒"))
    
    return(output_ras)
  }, error = function(e) {
    log_message(paste("处理失败:", e$message))
    return(NULL)
  })
}

# ----------------------
# 主处理流程
# ----------------------

# 初始化修复后的波段列表
repaired_bands <- list()
success_count <- 0

log_message(paste("处理波段数量:", length(band_files)))

# 逐个处理波段
for (i in seq_along(band_files)) {
  band <- band_files[i]
  ref_band <- ref_band_files[i]
  
  log_message(paste("\n--- 处理波段", i, "/", length(band_files), ":", band, "---"))
  
  # 修复波段
  repaired <- repair_band_with_adjustment(band, ref_band)
  
  if (!is.null(repaired)) {
    # 保存到列表
    repaired_bands[[length(repaired_bands) + 1]] <- repaired
    success_count <- success_count + 1
    
    # 保存单波段文件
    output_name <- paste0("repaired_", tools::file_path_sans_ext(band), ".tif")
    output_path <- file.path(output_dir, output_name)
    
    writeRaster(
      repaired,
      output_path,
      format = "GTiff",
      datatype = dataType(repaired),
      overwrite = TRUE,
      options = c("COMPRESS=LZW", "BIGTIFF=IF_SAFER")
    )
    
    log_message(paste("已保存:", output_path))
  }
  
  # 清理内存
  gc()
}

# ----------------------
# 创建多波段合成图像
# ----------------------

if (success_count > 0) {
  log_message("\n创建多波段合成图像...")
  
  # 创建堆栈
  band_stack <- stack(repaired_bands)
  
  # 设置波段名称
  band_names <- c("Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2")[1:length(repaired_bands)]
  names(band_stack) <- band_names
  
  # 保存合成图像
  composite_path <- file.path(output_dir, "landsat_composite.tif")
  writeRaster(
    band_stack,
    composite_path,
    format = "GTiff",
    datatype = dataType(repaired_bands[[1]]),
    overwrite = TRUE,
    options = c("COMPRESS=LZW", "BIGTIFF=IF_SAFER")
  )
  
  log_message(paste("合成图像已保存:", composite_path))
  
  # 生成预览图
  log_message("\n生成预览图...")
  preview_path <- file.path(output_dir, "landsat_preview.png")
  png(preview_path, width = 1000, height = 800)
  
  if (nlayers(band_stack) >= 3) {
    plotRGB(band_stack, r = 3, g = 2, b = 1, stretch = "lin", 
            main = "修复后的Landsat图像")
  } else if (nlayers(band_stack) > 0) {
    plot(band_stack[[1]], main = "修复后的Landsat波段")
  }
  
  dev.off()
  log_message(paste("预览图已保存:", preview_path))
} else {
  log_message("\n警告: 没有成功修复的波段")
}

# ----------------------
# 完成报告
# ----------------------

log_message("\n======= 处理完成! =======")
log_message(paste("成功修复波段:", success_count, "/", length(band_files)))
log_message(paste("输出文件位置:", output_dir))
log_message(paste("日志文件:", log_file))

# 关闭日志
sink()















# 设置工作目录
setwd("D:/LE0709")

# 定义原始波段文件
band_files <- c("B1.tif", "B2.tif", "B3.tif", "B4.tif", "B5.tif", "B7.tif")

# 定义参照波段前缀
ref_prefix <- "Ref_"

# 创建输出目录
output_dir <- "Repaired_Output"
if (!dir.exists(output_dir)) {
  dir.create(output_dir)
}

# 创建日志文件
log_file <- file.path(output_dir, "repair_log.txt")
sink(log_file, split = TRUE)  # 同时输出到控制台和日志文件

# ----------------------
# 日志记录函数
# ----------------------

log_message <- function(message) {
  timestamp <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  cat(paste0("[", timestamp, "] ", message, "\n"))
}

# ----------------------
# 尺寸调整函数
# ----------------------

adjust_raster_size <- function(main_raster, ref_raster) {
  # 检查尺寸是否匹配
  if (all(dim(main_raster) == dim(ref_raster))) {
    return(main_raster)
  }
  
  log_message(paste("尺寸不匹配: 原始", dim(main_raster), "参照", dim(ref_raster)))
  log_message("正在进行尺寸调整...")
  
  # 创建目标栅格模板
  target_template <- ref_raster
  
  # 重采样主栅格以匹配参照栅格
  resampled_raster <- resample(main_raster, target_template, method = "bilinear")
  
  log_message(paste("调整后尺寸:", dim(resampled_raster)))
  
  return(resampled_raster)
}

# ----------------------
# 文件检查与加载
# ----------------------

log_message("======= 开始Landsat条带修复 =======")
log_message(paste("工作目录:", getwd()))
log_message(paste("输出目录:", output_dir))

# 检查文件存在性
check_files <- function(files) {
  missing_files <- character(0)
  
  for (f in files) {
    if (!file.exists(f)) {
      missing_files <- c(missing_files, f)
    }
  }
  
  if (length(missing_files) > 0) {
    log_message("错误: 以下文件缺失:")
    for (f in missing_files) {
      log_message(paste(" -", f))
    }
    return(FALSE)
  }
  return(TRUE)
}

# 生成参照波段文件列表
ref_band_files <- paste0(ref_prefix, band_files)

# 验证所有文件
all_files <- c(band_files, ref_band_files)
if (!check_files(all_files)) {
  stop("文件缺失，请检查工作目录")
} else {
  log_message("所有文件存在性验证通过")
}

# ----------------------
# 核心修复函数 (带尺寸调整)
# ----------------------

repair_band_with_adjustment <- function(input_file, ref_file) {
  start_time <- Sys.time()
  log_message(paste(">>> 开始处理波段:", basename(input_file)))
  log_message(paste("参照波段:", basename(ref_file)))
  
  tryCatch({
    # 读取栅格数据
    band_ras <- raster(input_file)
    ref_ras <- raster(ref_file)
    
    # 记录原始尺寸
    original_dim <- dim(band_ras)
    
    # 调整尺寸以匹配参照波段
    band_ras <- adjust_raster_size(band_ras, ref_ras)
    
    # 记录栅格信息
    log_message(paste("调整后尺寸:", dim(band_ras)))
    log_message(paste("参照波段尺寸:", dim(ref_ras)))
    log_message(paste("原始数据类型:", dataType(band_ras)))
    
    # 创建输出栅格
    output_ras <- raster(band_ras)
    
    # 将0值设为NA（表示缺失）
    band_ras[band_ras == 0] <- NA
    
    # 转换为矩阵
    band_mat <- as.matrix(band_ras)
    ref_mat <- as.matrix(ref_ras)
    
    # 获取缺失掩膜
    na_mask <- is.na(band_mat)
    na_count <- sum(na_mask)
    total_pixels <- length(band_mat)
    
    if (na_count == 0) {
      log_message("没有缺失值，跳过修复")
      return(band_ras)
    }
    
    log_message(paste("缺失像素:", na_count, "(", round(100 * na_count/total_pixels, 2), "%)"))
    
    # 步骤1: 垂直插值
    log_message("步骤1: 垂直插值...")
    band_mat <- apply(band_mat, 2, function(col) {
      na.approx(col, na.rm = FALSE, rule = 2, maxgap = 10)
    })
    
    # 步骤2: 水平插值 (修复语法错误)
    log_message("步骤2: 水平插值...")
    band_mat <- t(apply(band_mat, 1, function(row) {
      na.approx(row, na.rm = FALSE, rule = 2, maxgap = 10)
    }))  # 修复：添加了缺失的括号
    
    # 步骤3: 修复剩余缺失值
    remaining_na <- sum(is.na(band_mat))
    if (remaining_na > 0) {
      log_message(paste("步骤3: 修复剩余缺失值 (", remaining_na, "像素)"))
      
      # 使用参照值填充剩余缺失
      band_mat[is.na(band_mat)] <- ref_mat[is.na(band_mat)]
    }
    
    # 创建修复后的栅格
    values(output_ras) <- as.vector(t(band_mat))
    
    # 保持原始数据类型
    original_dtype <- dataType(band_ras)
    if (original_dtype %in% c("INT2U", "INT2S")) {
      vals <- getValues(output_ras)
      if (original_dtype == "INT2U") {
        vals <- round(pmin(pmax(vals, 0), 65535))
      } else {
        vals <- round(pmin(pmax(vals, -32768), 32767))
      }
      output_ras <- setValues(output_ras, vals)
      dataType(output_ras) <- original_dtype
    }
    
    # 计算处理时间
    time_taken <- round(as.numeric(difftime(Sys.time(), start_time, units = "secs")), 1)
    log_message(paste("<<< 处理成功! 耗时:", time_taken, "秒"))
    
    return(output_ras)
  }, error = function(e) {
    log_message(paste("处理失败:", e$message))
    return(NULL)
  })
}

# ----------------------
# 主处理流程
# ----------------------

# 初始化修复后的波段列表
repaired_bands <- list()
success_count <- 0

log_message(paste("处理波段数量:", length(band_files)))

# 逐个处理波段
for (i in seq_along(band_files)) {
  band <- band_files[i]
  ref_band <- ref_band_files[i]
  
  log_message(paste("\n--- 处理波段", i, "/", length(band_files), ":", band, "---"))
  
  # 修复波段
  repaired <- repair_band_with_adjustment(band, ref_band)
  
  if (!is.null(repaired)) {
    # 保存到列表
    repaired_bands[[length(repaired_bands) + 1]] <- repaired
    success_count <- success_count + 1
    
    # 保存单波段文件
    output_name <- paste0("repaired_", tools::file_path_sans_ext(band), ".tif")
    output_path <- file.path(output_dir, output_name)
    
    writeRaster(
      repaired,
      output_path,
      format = "GTiff",
      datatype = dataType(repaired),
      overwrite = TRUE,
      options = c("COMPRESS=LZW", "BIGTIFF=IF_SAFER")
    )
    
    log_message(paste("已保存:", output_path))
  }
  
  # 清理内存
  gc()
}

# ----------------------
# 创建多波段合成图像
# ----------------------

if (success_count > 0) {
  log_message("\n创建多波段合成图像...")
  
  # 创建堆栈
  band_stack <- stack(repaired_bands)
  
  # 设置波段名称
  band_names <- c("Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2")[1:length(repaired_bands)]
  names(band_stack) <- band_names
  
  # 保存合成图像
  composite_path <- file.path(output_dir, "landsat_composite.tif")
  writeRaster(
    band_stack,
    composite_path,
    format = "GTiff",
    datatype = dataType(repaired_bands[[1]]),
    overwrite = TRUE,
    options = c("COMPRESS=LZW", "BIGTIFF=IF_SAFER")
  )
  
  log_message(paste("合成图像已保存:", composite_path))
  
  # 生成预览图
  log_message("\n生成预览图...")
  preview_path <- file.path(output_dir, "landsat_preview.png")
  png(preview_path, width = 1000, height = 800)
  
  if (nlayers(band_stack) >= 3) {
    plotRGB(band_stack, r = 3, g = 2, b = 1, stretch = "lin", 
            main = "修复后的Landsat图像")
  } else if (nlayers(band_stack) > 0) {
    plot(band_stack[[1]], main = "修复后的Landsat波段")
  }
  
  dev.off()
  log_message(paste("预览图已保存:", preview_path))
} else {
  log_message("\n警告: 没有成功修复的波段")
}

# ----------------------
# 完成报告
# ----------------------

log_message("\n======= 处理完成! =======")
log_message(paste("成功修复波段:", success_count, "/", length(band_files)))
log_message(paste("输出文件位置:", output_dir))
log_message(paste("日志文件:", log_file))

# 关闭日志
sink()
















# 设置工作目录
setwd("D:/LE0710")

# 定义原始波段文件
band_files <- c("B1.tif", "B2.tif", "B3.tif", "B4.tif", "B5.tif", "B7.tif")

# 定义参照波段前缀
ref_prefix <- "Ref_"

# 创建输出目录
output_dir <- "Repaired_Output"
if (!dir.exists(output_dir)) {
  dir.create(output_dir)
}

# 创建日志文件
log_file <- file.path(output_dir, "repair_log.txt")
sink(log_file, split = TRUE)  # 同时输出到控制台和日志文件

# ----------------------
# 日志记录函数
# ----------------------

log_message <- function(message) {
  timestamp <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  cat(paste0("[", timestamp, "] ", message, "\n"))
}

# ----------------------
# 尺寸调整函数
# ----------------------

adjust_raster_size <- function(main_raster, ref_raster) {
  # 检查尺寸是否匹配
  if (all(dim(main_raster) == dim(ref_raster))) {
    return(main_raster)
  }
  
  log_message(paste("尺寸不匹配: 原始", dim(main_raster), "参照", dim(ref_raster)))
  log_message("正在进行尺寸调整...")
  
  # 创建目标栅格模板
  target_template <- ref_raster
  
  # 重采样主栅格以匹配参照栅格
  resampled_raster <- resample(main_raster, target_template, method = "bilinear")
  
  log_message(paste("调整后尺寸:", dim(resampled_raster)))
  
  return(resampled_raster)
}

# ----------------------
# 文件检查与加载
# ----------------------

log_message("======= 开始Landsat条带修复 =======")
log_message(paste("工作目录:", getwd()))
log_message(paste("输出目录:", output_dir))

# 检查文件存在性
check_files <- function(files) {
  missing_files <- character(0)
  
  for (f in files) {
    if (!file.exists(f)) {
      missing_files <- c(missing_files, f)
    }
  }
  
  if (length(missing_files) > 0) {
    log_message("错误: 以下文件缺失:")
    for (f in missing_files) {
      log_message(paste(" -", f))
    }
    return(FALSE)
  }
  return(TRUE)
}

# 生成参照波段文件列表
ref_band_files <- paste0(ref_prefix, band_files)

# 验证所有文件
all_files <- c(band_files, ref_band_files)
if (!check_files(all_files)) {
  stop("文件缺失，请检查工作目录")
} else {
  log_message("所有文件存在性验证通过")
}

# ----------------------
# 核心修复函数 (带尺寸调整)
# ----------------------

repair_band_with_adjustment <- function(input_file, ref_file) {
  start_time <- Sys.time()
  log_message(paste(">>> 开始处理波段:", basename(input_file)))
  log_message(paste("参照波段:", basename(ref_file)))
  
  tryCatch({
    # 读取栅格数据
    band_ras <- raster(input_file)
    ref_ras <- raster(ref_file)
    
    # 记录原始尺寸
    original_dim <- dim(band_ras)
    
    # 调整尺寸以匹配参照波段
    band_ras <- adjust_raster_size(band_ras, ref_ras)
    
    # 记录栅格信息
    log_message(paste("调整后尺寸:", dim(band_ras)))
    log_message(paste("参照波段尺寸:", dim(ref_ras)))
    log_message(paste("原始数据类型:", dataType(band_ras)))
    
    # 创建输出栅格
    output_ras <- raster(band_ras)
    
    # 将0值设为NA（表示缺失）
    band_ras[band_ras == 0] <- NA
    
    # 转换为矩阵
    band_mat <- as.matrix(band_ras)
    ref_mat <- as.matrix(ref_ras)
    
    # 获取缺失掩膜
    na_mask <- is.na(band_mat)
    na_count <- sum(na_mask)
    total_pixels <- length(band_mat)
    
    if (na_count == 0) {
      log_message("没有缺失值，跳过修复")
      return(band_ras)
    }
    
    log_message(paste("缺失像素:", na_count, "(", round(100 * na_count/total_pixels, 2), "%)"))
    
    # 步骤1: 垂直插值
    log_message("步骤1: 垂直插值...")
    band_mat <- apply(band_mat, 2, function(col) {
      na.approx(col, na.rm = FALSE, rule = 2, maxgap = 10)
    })
    
    # 步骤2: 水平插值 (修复语法错误)
    log_message("步骤2: 水平插值...")
    band_mat <- t(apply(band_mat, 1, function(row) {
      na.approx(row, na.rm = FALSE, rule = 2, maxgap = 10)
    }))  # 修复：添加了缺失的括号
    
    # 步骤3: 修复剩余缺失值
    remaining_na <- sum(is.na(band_mat))
    if (remaining_na > 0) {
      log_message(paste("步骤3: 修复剩余缺失值 (", remaining_na, "像素)"))
      
      # 使用参照值填充剩余缺失
      band_mat[is.na(band_mat)] <- ref_mat[is.na(band_mat)]
    }
    
    # 创建修复后的栅格
    values(output_ras) <- as.vector(t(band_mat))
    
    # 保持原始数据类型
    original_dtype <- dataType(band_ras)
    if (original_dtype %in% c("INT2U", "INT2S")) {
      vals <- getValues(output_ras)
      if (original_dtype == "INT2U") {
        vals <- round(pmin(pmax(vals, 0), 65535))
      } else {
        vals <- round(pmin(pmax(vals, -32768), 32767))
      }
      output_ras <- setValues(output_ras, vals)
      dataType(output_ras) <- original_dtype
    }
    
    # 计算处理时间
    time_taken <- round(as.numeric(difftime(Sys.time(), start_time, units = "secs")), 1)
    log_message(paste("<<< 处理成功! 耗时:", time_taken, "秒"))
    
    return(output_ras)
  }, error = function(e) {
    log_message(paste("处理失败:", e$message))
    return(NULL)
  })
}

# ----------------------
# 主处理流程
# ----------------------

# 初始化修复后的波段列表
repaired_bands <- list()
success_count <- 0

log_message(paste("处理波段数量:", length(band_files)))

# 逐个处理波段
for (i in seq_along(band_files)) {
  band <- band_files[i]
  ref_band <- ref_band_files[i]
  
  log_message(paste("\n--- 处理波段", i, "/", length(band_files), ":", band, "---"))
  
  # 修复波段
  repaired <- repair_band_with_adjustment(band, ref_band)
  
  if (!is.null(repaired)) {
    # 保存到列表
    repaired_bands[[length(repaired_bands) + 1]] <- repaired
    success_count <- success_count + 1
    
    # 保存单波段文件
    output_name <- paste0("repaired_", tools::file_path_sans_ext(band), ".tif")
    output_path <- file.path(output_dir, output_name)
    
    writeRaster(
      repaired,
      output_path,
      format = "GTiff",
      datatype = dataType(repaired),
      overwrite = TRUE,
      options = c("COMPRESS=LZW", "BIGTIFF=IF_SAFER")
    )
    
    log_message(paste("已保存:", output_path))
  }
  
  # 清理内存
  gc()
}

# ----------------------
# 创建多波段合成图像
# ----------------------

if (success_count > 0) {
  log_message("\n创建多波段合成图像...")
  
  # 创建堆栈
  band_stack <- stack(repaired_bands)
  
  # 设置波段名称
  band_names <- c("Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2")[1:length(repaired_bands)]
  names(band_stack) <- band_names
  
  # 保存合成图像
  composite_path <- file.path(output_dir, "landsat_composite.tif")
  writeRaster(
    band_stack,
    composite_path,
    format = "GTiff",
    datatype = dataType(repaired_bands[[1]]),
    overwrite = TRUE,
    options = c("COMPRESS=LZW", "BIGTIFF=IF_SAFER")
  )
  
  log_message(paste("合成图像已保存:", composite_path))
  
  # 生成预览图
  log_message("\n生成预览图...")
  preview_path <- file.path(output_dir, "landsat_preview.png")
  png(preview_path, width = 1000, height = 800)
  
  if (nlayers(band_stack) >= 3) {
    plotRGB(band_stack, r = 3, g = 2, b = 1, stretch = "lin", 
            main = "修复后的Landsat图像")
  } else if (nlayers(band_stack) > 0) {
    plot(band_stack[[1]], main = "修复后的Landsat波段")
  }
  
  dev.off()
  log_message(paste("预览图已保存:", preview_path))
} else {
  log_message("\n警告: 没有成功修复的波段")
}

# ----------------------
# 完成报告
# ----------------------

log_message("\n======= 处理完成! =======")
log_message(paste("成功修复波段:", success_count, "/", length(band_files)))
log_message(paste("输出文件位置:", output_dir))
log_message(paste("日志文件:", log_file))

# 关闭日志
sink()















# 设置工作目录
setwd("D:/LE0711")

# 定义原始波段文件
band_files <- c("B1.tif", "B2.tif", "B3.tif", "B4.tif", "B5.tif", "B7.tif")

# 定义参照波段前缀
ref_prefix <- "Ref_"

# 创建输出目录
output_dir <- "Repaired_Output"
if (!dir.exists(output_dir)) {
  dir.create(output_dir)
}

# 创建日志文件
log_file <- file.path(output_dir, "repair_log.txt")
sink(log_file, split = TRUE)  # 同时输出到控制台和日志文件

# ----------------------
# 日志记录函数
# ----------------------

log_message <- function(message) {
  timestamp <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  cat(paste0("[", timestamp, "] ", message, "\n"))
}

# ----------------------
# 尺寸调整函数
# ----------------------

adjust_raster_size <- function(main_raster, ref_raster) {
  # 检查尺寸是否匹配
  if (all(dim(main_raster) == dim(ref_raster))) {
    return(main_raster)
  }
  
  log_message(paste("尺寸不匹配: 原始", dim(main_raster), "参照", dim(ref_raster)))
  log_message("正在进行尺寸调整...")
  
  # 创建目标栅格模板
  target_template <- ref_raster
  
  # 重采样主栅格以匹配参照栅格
  resampled_raster <- resample(main_raster, target_template, method = "bilinear")
  
  log_message(paste("调整后尺寸:", dim(resampled_raster)))
  
  return(resampled_raster)
}

# ----------------------
# 文件检查与加载
# ----------------------

log_message("======= 开始Landsat条带修复 =======")
log_message(paste("工作目录:", getwd()))
log_message(paste("输出目录:", output_dir))

# 检查文件存在性
check_files <- function(files) {
  missing_files <- character(0)
  
  for (f in files) {
    if (!file.exists(f)) {
      missing_files <- c(missing_files, f)
    }
  }
  
  if (length(missing_files) > 0) {
    log_message("错误: 以下文件缺失:")
    for (f in missing_files) {
      log_message(paste(" -", f))
    }
    return(FALSE)
  }
  return(TRUE)
}

# 生成参照波段文件列表
ref_band_files <- paste0(ref_prefix, band_files)

# 验证所有文件
all_files <- c(band_files, ref_band_files)
if (!check_files(all_files)) {
  stop("文件缺失，请检查工作目录")
} else {
  log_message("所有文件存在性验证通过")
}

# ----------------------
# 核心修复函数 (带尺寸调整)
# ----------------------

repair_band_with_adjustment <- function(input_file, ref_file) {
  start_time <- Sys.time()
  log_message(paste(">>> 开始处理波段:", basename(input_file)))
  log_message(paste("参照波段:", basename(ref_file)))
  
  tryCatch({
    # 读取栅格数据
    band_ras <- raster(input_file)
    ref_ras <- raster(ref_file)
    
    # 记录原始尺寸
    original_dim <- dim(band_ras)
    
    # 调整尺寸以匹配参照波段
    band_ras <- adjust_raster_size(band_ras, ref_ras)
    
    # 记录栅格信息
    log_message(paste("调整后尺寸:", dim(band_ras)))
    log_message(paste("参照波段尺寸:", dim(ref_ras)))
    log_message(paste("原始数据类型:", dataType(band_ras)))
    
    # 创建输出栅格
    output_ras <- raster(band_ras)
    
    # 将0值设为NA（表示缺失）
    band_ras[band_ras == 0] <- NA
    
    # 转换为矩阵
    band_mat <- as.matrix(band_ras)
    ref_mat <- as.matrix(ref_ras)
    
    # 获取缺失掩膜
    na_mask <- is.na(band_mat)
    na_count <- sum(na_mask)
    total_pixels <- length(band_mat)
    
    if (na_count == 0) {
      log_message("没有缺失值，跳过修复")
      return(band_ras)
    }
    
    log_message(paste("缺失像素:", na_count, "(", round(100 * na_count/total_pixels, 2), "%)"))
    
    # 步骤1: 垂直插值
    log_message("步骤1: 垂直插值...")
    band_mat <- apply(band_mat, 2, function(col) {
      na.approx(col, na.rm = FALSE, rule = 2, maxgap = 10)
    })
    
    # 步骤2: 水平插值 (修复语法错误)
    log_message("步骤2: 水平插值...")
    band_mat <- t(apply(band_mat, 1, function(row) {
      na.approx(row, na.rm = FALSE, rule = 2, maxgap = 10)
    }))  # 修复：添加了缺失的括号
    
    # 步骤3: 修复剩余缺失值
    remaining_na <- sum(is.na(band_mat))
    if (remaining_na > 0) {
      log_message(paste("步骤3: 修复剩余缺失值 (", remaining_na, "像素)"))
      
      # 使用参照值填充剩余缺失
      band_mat[is.na(band_mat)] <- ref_mat[is.na(band_mat)]
    }
    
    # 创建修复后的栅格
    values(output_ras) <- as.vector(t(band_mat))
    
    # 保持原始数据类型
    original_dtype <- dataType(band_ras)
    if (original_dtype %in% c("INT2U", "INT2S")) {
      vals <- getValues(output_ras)
      if (original_dtype == "INT2U") {
        vals <- round(pmin(pmax(vals, 0), 65535))
      } else {
        vals <- round(pmin(pmax(vals, -32768), 32767))
      }
      output_ras <- setValues(output_ras, vals)
      dataType(output_ras) <- original_dtype
    }
    
    # 计算处理时间
    time_taken <- round(as.numeric(difftime(Sys.time(), start_time, units = "secs")), 1)
    log_message(paste("<<< 处理成功! 耗时:", time_taken, "秒"))
    
    return(output_ras)
  }, error = function(e) {
    log_message(paste("处理失败:", e$message))
    return(NULL)
  })
}

# ----------------------
# 主处理流程
# ----------------------

# 初始化修复后的波段列表
repaired_bands <- list()
success_count <- 0

log_message(paste("处理波段数量:", length(band_files)))

# 逐个处理波段
for (i in seq_along(band_files)) {
  band <- band_files[i]
  ref_band <- ref_band_files[i]
  
  log_message(paste("\n--- 处理波段", i, "/", length(band_files), ":", band, "---"))
  
  # 修复波段
  repaired <- repair_band_with_adjustment(band, ref_band)
  
  if (!is.null(repaired)) {
    # 保存到列表
    repaired_bands[[length(repaired_bands) + 1]] <- repaired
    success_count <- success_count + 1
    
    # 保存单波段文件
    output_name <- paste0("repaired_", tools::file_path_sans_ext(band), ".tif")
    output_path <- file.path(output_dir, output_name)
    
    writeRaster(
      repaired,
      output_path,
      format = "GTiff",
      datatype = dataType(repaired),
      overwrite = TRUE,
      options = c("COMPRESS=LZW", "BIGTIFF=IF_SAFER")
    )
    
    log_message(paste("已保存:", output_path))
  }
  
  # 清理内存
  gc()
}

# ----------------------
# 创建多波段合成图像
# ----------------------

if (success_count > 0) {
  log_message("\n创建多波段合成图像...")
  
  # 创建堆栈
  band_stack <- stack(repaired_bands)
  
  # 设置波段名称
  band_names <- c("Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2")[1:length(repaired_bands)]
  names(band_stack) <- band_names
  
  # 保存合成图像
  composite_path <- file.path(output_dir, "landsat_composite.tif")
  writeRaster(
    band_stack,
    composite_path,
    format = "GTiff",
    datatype = dataType(repaired_bands[[1]]),
    overwrite = TRUE,
    options = c("COMPRESS=LZW", "BIGTIFF=IF_SAFER")
  )
  
  log_message(paste("合成图像已保存:", composite_path))
  
  # 生成预览图
  log_message("\n生成预览图...")
  preview_path <- file.path(output_dir, "landsat_preview.png")
  png(preview_path, width = 1000, height = 800)
  
  if (nlayers(band_stack) >= 3) {
    plotRGB(band_stack, r = 3, g = 2, b = 1, stretch = "lin", 
            main = "修复后的Landsat图像")
  } else if (nlayers(band_stack) > 0) {
    plot(band_stack[[1]], main = "修复后的Landsat波段")
  }
  
  dev.off()
  log_message(paste("预览图已保存:", preview_path))
} else {
  log_message("\n警告: 没有成功修复的波段")
}

# ----------------------
# 完成报告
# ----------------------

log_message("\n======= 处理完成! =======")
log_message(paste("成功修复波段:", success_count, "/", length(band_files)))
log_message(paste("输出文件位置:", output_dir))
log_message(paste("日志文件:", log_file))

# 关闭日志
sink()











# 设置工作目录
setwd("D:/LE0712")

# 定义原始波段文件
band_files <- c("B1.tif", "B2.tif", "B3.tif", "B4.tif", "B5.tif", "B7.tif")

# 定义参照波段前缀
ref_prefix <- "Ref_"

# 创建输出目录
output_dir <- "Repaired_Output"
if (!dir.exists(output_dir)) {
  dir.create(output_dir)
}

# 创建日志文件
log_file <- file.path(output_dir, "repair_log.txt")
sink(log_file, split = TRUE)  # 同时输出到控制台和日志文件

# ----------------------
# 日志记录函数
# ----------------------

log_message <- function(message) {
  timestamp <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
  cat(paste0("[", timestamp, "] ", message, "\n"))
}

# ----------------------
# 尺寸调整函数
# ----------------------

adjust_raster_size <- function(main_raster, ref_raster) {
  # 检查尺寸是否匹配
  if (all(dim(main_raster) == dim(ref_raster))) {
    return(main_raster)
  }
  
  log_message(paste("尺寸不匹配: 原始", dim(main_raster), "参照", dim(ref_raster)))
  log_message("正在进行尺寸调整...")
  
  # 创建目标栅格模板
  target_template <- ref_raster
  
  # 重采样主栅格以匹配参照栅格
  resampled_raster <- resample(main_raster, target_template, method = "bilinear")
  
  log_message(paste("调整后尺寸:", dim(resampled_raster)))
  
  return(resampled_raster)
}

# ----------------------
# 文件检查与加载
# ----------------------

log_message("======= 开始Landsat条带修复 =======")
log_message(paste("工作目录:", getwd()))
log_message(paste("输出目录:", output_dir))

# 检查文件存在性
check_files <- function(files) {
  missing_files <- character(0)
  
  for (f in files) {
    if (!file.exists(f)) {
      missing_files <- c(missing_files, f)
    }
  }
  
  if (length(missing_files) > 0) {
    log_message("错误: 以下文件缺失:")
    for (f in missing_files) {
      log_message(paste(" -", f))
    }
    return(FALSE)
  }
  return(TRUE)
}

# 生成参照波段文件列表
ref_band_files <- paste0(ref_prefix, band_files)

# 验证所有文件
all_files <- c(band_files, ref_band_files)
if (!check_files(all_files)) {
  stop("文件缺失，请检查工作目录")
} else {
  log_message("所有文件存在性验证通过")
}

# ----------------------
# 核心修复函数 (带尺寸调整)
# ----------------------

repair_band_with_adjustment <- function(input_file, ref_file) {
  start_time <- Sys.time()
  log_message(paste(">>> 开始处理波段:", basename(input_file)))
  log_message(paste("参照波段:", basename(ref_file)))
  
  tryCatch({
    # 读取栅格数据
    band_ras <- raster(input_file)
    ref_ras <- raster(ref_file)
    
    # 记录原始尺寸
    original_dim <- dim(band_ras)
    
    # 调整尺寸以匹配参照波段
    band_ras <- adjust_raster_size(band_ras, ref_ras)
    
    # 记录栅格信息
    log_message(paste("调整后尺寸:", dim(band_ras)))
    log_message(paste("参照波段尺寸:", dim(ref_ras)))
    log_message(paste("原始数据类型:", dataType(band_ras)))
    
    # 创建输出栅格
    output_ras <- raster(band_ras)
    
    # 将0值设为NA（表示缺失）
    band_ras[band_ras == 0] <- NA
    
    # 转换为矩阵
    band_mat <- as.matrix(band_ras)
    ref_mat <- as.matrix(ref_ras)
    
    # 获取缺失掩膜
    na_mask <- is.na(band_mat)
    na_count <- sum(na_mask)
    total_pixels <- length(band_mat)
    
    if (na_count == 0) {
      log_message("没有缺失值，跳过修复")
      return(band_ras)
    }
    
    log_message(paste("缺失像素:", na_count, "(", round(100 * na_count/total_pixels, 2), "%)"))
    
    # 步骤1: 垂直插值
    log_message("步骤1: 垂直插值...")
    band_mat <- apply(band_mat, 2, function(col) {
      na.approx(col, na.rm = FALSE, rule = 2, maxgap = 10)
    })
    
    # 步骤2: 水平插值 (修复语法错误)
    log_message("步骤2: 水平插值...")
    band_mat <- t(apply(band_mat, 1, function(row) {
      na.approx(row, na.rm = FALSE, rule = 2, maxgap = 10)
    }))  # 修复：添加了缺失的括号
    
    # 步骤3: 修复剩余缺失值
    remaining_na <- sum(is.na(band_mat))
    if (remaining_na > 0) {
      log_message(paste("步骤3: 修复剩余缺失值 (", remaining_na, "像素)"))
      
      # 使用参照值填充剩余缺失
      band_mat[is.na(band_mat)] <- ref_mat[is.na(band_mat)]
    }
    
    # 创建修复后的栅格
    values(output_ras) <- as.vector(t(band_mat))
    
    # 保持原始数据类型
    original_dtype <- dataType(band_ras)
    if (original_dtype %in% c("INT2U", "INT2S")) {
      vals <- getValues(output_ras)
      if (original_dtype == "INT2U") {
        vals <- round(pmin(pmax(vals, 0), 65535))
      } else {
        vals <- round(pmin(pmax(vals, -32768), 32767))
      }
      output_ras <- setValues(output_ras, vals)
      dataType(output_ras) <- original_dtype
    }
    
    # 计算处理时间
    time_taken <- round(as.numeric(difftime(Sys.time(), start_time, units = "secs")), 1)
    log_message(paste("<<< 处理成功! 耗时:", time_taken, "秒"))
    
    return(output_ras)
  }, error = function(e) {
    log_message(paste("处理失败:", e$message))
    return(NULL)
  })
}

# ----------------------
# 主处理流程
# ----------------------

# 初始化修复后的波段列表
repaired_bands <- list()
success_count <- 0

log_message(paste("处理波段数量:", length(band_files)))

# 逐个处理波段
for (i in seq_along(band_files)) {
  band <- band_files[i]
  ref_band <- ref_band_files[i]
  
  log_message(paste("\n--- 处理波段", i, "/", length(band_files), ":", band, "---"))
  
  # 修复波段
  repaired <- repair_band_with_adjustment(band, ref_band)
  
  if (!is.null(repaired)) {
    # 保存到列表
    repaired_bands[[length(repaired_bands) + 1]] <- repaired
    success_count <- success_count + 1
    
    # 保存单波段文件
    output_name <- paste0("repaired_", tools::file_path_sans_ext(band), ".tif")
    output_path <- file.path(output_dir, output_name)
    
    writeRaster(
      repaired,
      output_path,
      format = "GTiff",
      datatype = dataType(repaired),
      overwrite = TRUE,
      options = c("COMPRESS=LZW", "BIGTIFF=IF_SAFER")
    )
    
    log_message(paste("已保存:", output_path))
  }
  
  # 清理内存
  gc()
}

# ----------------------
# 创建多波段合成图像
# ----------------------

if (success_count > 0) {
  log_message("\n创建多波段合成图像...")
  
  # 创建堆栈
  band_stack <- stack(repaired_bands)
  
  # 设置波段名称
  band_names <- c("Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2")[1:length(repaired_bands)]
  names(band_stack) <- band_names
  
  # 保存合成图像
  composite_path <- file.path(output_dir, "landsat_composite.tif")
  writeRaster(
    band_stack,
    composite_path,
    format = "GTiff",
    datatype = dataType(repaired_bands[[1]]),
    overwrite = TRUE,
    options = c("COMPRESS=LZW", "BIGTIFF=IF_SAFER")
  )
  
  log_message(paste("合成图像已保存:", composite_path))
  
  # 生成预览图
  log_message("\n生成预览图...")
  preview_path <- file.path(output_dir, "landsat_preview.png")
  png(preview_path, width = 1000, height = 800)
  
  if (nlayers(band_stack) >= 3) {
    plotRGB(band_stack, r = 3, g = 2, b = 1, stretch = "lin", 
            main = "修复后的Landsat图像")
  } else if (nlayers(band_stack) > 0) {
    plot(band_stack[[1]], main = "修复后的Landsat波段")
  }
  
  dev.off()
  log_message(paste("预览图已保存:", preview_path))
} else {
  log_message("\n警告: 没有成功修复的波段")
}

# ----------------------
# 完成报告
# ----------------------

log_message("\n======= 处理完成! =======")
log_message(paste("成功修复波段:", success_count, "/", length(band_files)))
log_message(paste("输出文件位置:", output_dir))
log_message(paste("日志文件:", log_file))

# 关闭日志
sink()

