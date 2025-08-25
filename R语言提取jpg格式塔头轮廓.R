# 加载必要的包
library(imager)         # 图像处理
library(EBImage)        # 图像分析和特征提取
library(tidyverse)      # 数据处理和可视化

# 1. 图像加载与预处理 -----------------------------------------------------------
# 加载图像 (替换为实际文件路径)
image_path <- "D:/123.jpg"
original_img <- load.image(image_path)

# 转换为灰度图像
gray_img <- grayscale(original_img)

# 保存预处理图像
save.image(gray_img, "gray_image.jpg", quality = 0.9)

# 2. 斑状特征提取 -------------------------------------------------------------
# 使用Otsu方法自动计算最佳阈值
threshold_value <- EBImage::otsu(as.array(gray_img)[,,1,1])
binary_img <- gray_img > threshold_value

# 从二值图像中识别连通区域
blobs <- EBImage::bwlabel(as.array(binary_img)[,,1,1])

# 计算斑块属性
blob_props <- EBImage::computeFeatures.moment(blobs)
blob_shapes <- EBImage::computeFeatures.shape(blobs)

# 创建斑块属性数据框
blob_df <- data.frame(
  id = 1:nrow(blob_props),
  area = blob_shapes[, "s.area"],
  perimeter = blob_shapes[, "s.perimeter"],
  circularity = 4 * pi * blob_shapes[, "s.area"] / (blob_shapes[, "s.perimeter"]^2),
  centroid_x = blob_props[, "m.cx"],
  centroid_y = blob_props[, "m.cy"]
)

# 过滤小斑块（面积小于100像素）
significant_blobs <- blob_df %>% 
  filter(area > 100)

# 3. 创建斑块特征图像 ---------------------------------------------------------
# 方法A: 二值斑块图像（黑白）
# 创建空白图像
binary_tiff <- as.cimg(array(0, dim = dim(gray_img)[1:2]))

# 标记显著斑块 - 使用正确的循环结构
for (i in significant_blobs$id) {
  # 确保使用正确的坐标系统
  mask <- blobs == i
  binary_tiff[mask] <- 1
}

# 方法B: 彩色斑块图像（保留原图颜色）
# 创建空白RGB图像
width <- dim(original_img)[1]
height <- dim(original_img)[2]

# 创建正确维度的空白RGB图像
color_tiff <- imager::as.cimg(array(0, dim = c(width, height, 1, 3)))

# 为每个斑块填充原图颜色
for (i in significant_blobs$id) {
  # 获取斑块位置
  mask <- blobs == i
  
  # 扩展mask到4维以匹配RGB图像
  mask_4d <- array(mask, dim = c(dim(mask), 1, 1))
  mask_4d <- array(mask_4d, dim = c(dim(mask_4d)[1:2], 1, 3))
  
  # 提取原图对应区域
  color_tiff[mask_4d] <- original_img[mask_4d]
}

# 方法C: 斑块轮廓图像
# 创建空白图像
contour_tiff <- as.cimg(array(0, dim = dim(gray_img)[1:2]))

# 提取斑块轮廓
for (i in significant_blobs$id) {
  # 获取单个斑块
  single_blob <- blobs == i
  # 计算轮廓
  contour <- EBImage::ocontour(single_blob)
  # 绘制轮廓
  if (length(contour) > 0) {
    contour_points <- contour[[1]]
    # 注意坐标转换：EBImage使用(row, col)，imager使用(x, y)
    x_coords <- contour_points[, 2]  # 列坐标对应x
    y_coords <- contour_points[, 1]  # 行坐标对应y
    contour_tiff[cbind(x_coords, y_coords)] <- 1
  }
}

# 4. 保存斑块特征图像 ---------------------------------------------------------
# 保存二值斑块图像
save.image(binary_tiff, "D:/binary_blobs.jpg")

# 保存彩色斑块图像
save.image(color_tiff, "D:/color_blobs.jpg")

# 保存斑块轮廓图像
save.image(contour_tiff, "D:/blob_contours.jpg")

# 5. 斑块特征可视化与分析 -----------------------------------------------------
# 斑块属性统计
ggplot(significant_blobs, aes(area)) +
  geom_histogram(bins = 30, fill = "steelblue", alpha = 0.7) +
  labs(title = "斑块面积分布", x = "面积 (像素)", y = "数量") +
  theme_minimal()
ggsave("blob_area_distribution.jpg", width = 8, height = 6, dpi = 300)

# 斑块空间分布
ggplot(significant_blobs, aes(centroid_x, centroid_y, size = area, color = circularity)) +
  geom_point(alpha = 0.6) +
  scale_size_continuous(range = c(1, 8)) +
  scale_color_viridis_c(option = "C") +
  labs(title = "斑块空间分布", x = "X坐标", y = "Y坐标", 
       size = "面积", color = "圆形度") +
  theme_minimal() +
  coord_equal()
ggsave("blob_spatial_distribution.jpg", width = 10, height = 8, dpi = 300)

# 6. 导出斑块特征数据 ---------------------------------------------------------
# 导出斑块属性到CSV
write_csv(significant_blobs, "blob_features.csv")

# 创建组合图
par(mfrow = c(2, 2))
plot(original_img, main = "原始图像")
plot(as.cimg(binary_tiff), main = "二值斑块")
plot(color_tiff, main = "彩色斑块")
plot(as.cimg(contour_tiff), main = "斑块轮廓")
dev.copy(tiff, "blob_comparison.tiff", width = 10, height = 8, units = "in", res = 300)
dev.off()

cat("分析完成！\n",
    "1. 斑块特征图像已保存为TIFF格式:\n",
    "   - binary_blobs.tiff: 二值斑块图像\n",
    "   - color_blobs.tiff: 彩色斑块图像\n",
    "   - blob_contours.tiff: 斑块轮廓图像\n",
    "2. 斑块特征数据已保存到: blob_features.csv\n")