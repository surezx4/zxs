import numpy as np
from scipy.interpolate import griddata
import matplotlib.pyplot as plt
import os
import time
from tqdm import tqdm
from PIL import Image
import multiprocessing as mp
import warnings
import gc  # 垃圾回收模块
import psutil  # 内存监控

# 禁用警告
warnings.filterwarnings("ignore")

def memory_usage():
    """获取当前内存使用情况"""
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / (1024 * 1024)  # MB
    return mem

def load_tiff_in_chunks(tiff_path, max_memory_mb=2000):
    """
    分块加载TIFF文件以避免内存溢出
    """
    print(f"分块加载TIFF文件: {os.path.basename(tiff_path)}")
    start_mem = memory_usage()
    
    with Image.open(tiff_path) as img:
        # 获取图像尺寸
        width, height = img.size
        band_count = img.n_frames if img.n_frames > 1 else 1
        
        # 确定分块大小
        chunk_size = min(1024, width, height)  # 默认分块大小
        print(f"原始尺寸: {width}×{height}, 波段数: {band_count}")
        print(f"分块大小: {chunk_size}×{chunk_size}")
        
        # 创建空数组存储结果
        if band_count > 1:
            image_array = np.zeros((band_count, height, width), dtype=np.uint16)
        else:
            image_array = np.zeros((height, width), dtype=np.uint16)
        
        # 分块加载
        for band_idx in range(band_count):
            img.seek(band_idx)
            for y in range(0, height, chunk_size):
                h = min(chunk_size, height - y)
                for x in range(0, width, chunk_size):
                    w = min(chunk_size, width - x)
                    
                    # 读取分块
                    box = (x, y, x+w, y+h)
                    chunk = np.array(img.crop(box))
                    
                    # 存储到数组
                    if band_count > 1:
                        image_array[band_idx, y:y+h, x:x+w] = chunk
                    else:
                        image_array[y:y+h, x:x+w] = chunk
                    
                    # 释放内存
                    del chunk
                    gc.collect()
        
        print(f"加载完成! 内存使用: {memory_usage() - start_mem:.2f} MB")
        return image_array

def save_array_as_tiff(array, output_path):
    """将NumPy数组保存为TIFF文件（分块保存）"""
    print(f"保存修复后的图像到: {output_path}")
    start_mem = memory_usage()
    
    # 单波段图像
    if array.ndim == 2:
        img = Image.fromarray(array)
        img.save(output_path, format='TIFF')
        return output_path
    
    # 多波段图像
    images = []
    for band_idx in range(array.shape[0]):
        band_img = Image.fromarray(array[band_idx])
        images.append(band_img)
    
    # 保存第一波段
    images[0].save(output_path, format='TIFF', save_all=True)
    
    # 追加其他波段
    for i in range(1, len(images)):
        with Image.open(output_path) as img:
            img.save(output_path, format='TIFF', save_all=True, append_images=[images[i]])
    
    print(f"保存完成! 内存使用: {memory_usage() - start_mem:.2f} MB")
    return output_path

def fix_landsat7_band(chunk_info):
    """修复单个条带区块（用于并行处理）"""
    chunk, x_start, y_start, width, height, buffer_size, missing_value = chunk_info
    
    try:
        # 如果整个区块都是缺失值，则跳过处理
        if np.all(chunk == missing_value):
            return x_start, y_start, chunk[buffer_size:buffer_size+height, buffer_size:buffer_size+width]
        
        # 创建缓冲区内的坐标网格
        rows, cols = chunk.shape
        y, x = np.mgrid[0:rows, 0:cols]
        
        # 识别缺失像素
        missing_mask = (chunk == missing_value)
        
        # 如果没有缺失值，直接返回结果
        if not np.any(missing_mask):
            return x_start, y_start, chunk[buffer_size:buffer_size+height, buffer_size:buffer_size+width]
        
        # 获取已知点（非缺失值）
        known_points = np.column_stack([
            y[~missing_mask].ravel(), 
            x[~missing_mask].ravel()
        ])
        known_values = chunk[~missing_mask].ravel()
        
        # 获取缺失点位置
        missing_points = np.column_stack([
            y[missing_mask].ravel(), 
            x[missing_mask].ravel()
        ])
        
        # 使用最近邻插值填补缺失值
        if known_points.size > 0 and missing_points.size > 0:
            filled_values = griddata(
                known_points, 
                known_values, 
                missing_points, 
                method='nearest'
            )
            
            # 将填补的值放回原数组
            filled_chunk = chunk.copy()
            filled_chunk[missing_mask] = filled_values
        else:
            filled_chunk = chunk
        
        # 提取无缓冲区区域
        result = filled_chunk[buffer_size:buffer_size+height, buffer_size:buffer_size+width]
        return x_start, y_start, result
    
    except Exception as e:
        print(f"区块处理错误 @ ({x_start},{y_start}): {str(e)}")
        # 返回原始区块作为后备
        return x_start, y_start, chunk[buffer_size:buffer_size+height, buffer_size:buffer_size+width]

def process_band_optimized(band_data, band_idx, band_count, height, width, chunk_size=256, buffer_size=32, missing_value=0):
    """优化后的波段处理函数"""
    print(f"处理波段 {band_idx+1}/{band_count}...")
    band_start = time.time()
    start_mem = memory_usage()
    
    # 创建输出数组
    fixed_band = np.zeros((height, width), dtype=band_data.dtype)
    
    # 准备并行处理任务
    tasks = []
    for y_offset in range(0, height, chunk_size):
        # 计算当前块的实际高度
        current_height = min(chunk_size, height - y_offset)
        
        for x_offset in range(0, width, chunk_size):
            # 计算当前块的实际宽度
            current_width = min(chunk_size, width - x_offset)
            
            # 计算带缓冲区的读取范围
            buf_y_start = max(0, y_offset - buffer_size)
            buf_y_end = min(height, y_offset + current_height + buffer_size)
            buf_x_start = max(0, x_offset - buffer_size)
            buf_x_end = min(width, x_offset + current_width + buffer_size)
            
            # 提取带缓冲区的区块
            chunk = band_data[buf_y_start:buf_y_end, buf_x_start:buf_x_end]
            
            # 添加到任务列表
            tasks.append((
                chunk, 
                x_offset, 
                y_offset, 
                current_width, 
                current_height, 
                buffer_size, 
                missing_value
            ))
    
    # 确定并行进程数（限制内存使用）
    num_cores = mp.cpu_count()
    # 使用更少的进程以避免内存溢出
    num_processes = max(1, min(4, num_cores // 2))  # 限制最大4进程
    
    print(f"  使用 {num_processes} 个进程处理 {len(tasks)} 个区块...")
    print(f"  当前内存: {memory_usage():.2f} MB")
    
    # 并行处理区块
    results = []
    with mp.Pool(processes=num_processes) as pool:
        # 分批处理任务以避免内存峰值
        batch_size = 50  # 每批处理的任务数
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i+batch_size]
            batch_results = list(tqdm(pool.imap(fix_landsat7_band, batch), total=len(batch)))
            results.extend(batch_results)
            
            # 释放内存
            del batch
            del batch_results
            gc.collect()
            print(f"  批处理 {i//batch_size+1}/{(len(tasks)+batch_size-1)//batch_size} 完成, 内存: {memory_usage():.2f} MB")
    
    # 将处理结果组合到输出数组中
    for x_offset, y_offset, result_chunk in results:
        h, w = result_chunk.shape
        fixed_band[y_offset:y_offset+h, x_offset:x_offset+w] = result_chunk
    
    # 释放内存
    del tasks
    del results
    gc.collect()
    
    print(f"  波段 {band_idx+1} 处理完成, 耗时: {time.time() - band_start:.2f}秒")
    print(f"  内存变化: {memory_usage() - start_mem:.2f} MB")
    return fixed_band

def fix_landsat7_tiff_optimized(input_path, output_path, chunk_size=256, buffer_size=32, missing_value=0):
    """
    修复 Landsat 7 条带问题（内存优化版）
    """
    print(f"开始处理: {os.path.basename(input_path)}")
    start_time = time.time()
    start_mem = memory_usage()
    
    # 加载 TIFF 文件为数组
    print("加载 TIFF 文件...")
    image_array = load_tiff_in_chunks(input_path)
    
    # 确定图像尺寸和波段数
    if image_array.ndim == 2:
        # 单波段图像
        height, width = image_array.shape
        band_count = 1
    elif image_array.ndim == 3:
        # 多波段图像 (bands, height, width)
        band_count, height, width = image_array.shape
    else:
        raise ValueError("不支持的图像维度")
    
    print(f"图像尺寸: {width}×{height}, 波段数: {band_count}")
    
    # 创建输出数组
    fixed_image = np.zeros((band_count, height, width), dtype=image_array.dtype)
    
    # 处理每个波段
    for band_idx in range(band_count):
        # 获取当前波段数据
        if band_count == 1:
            band_data = image_array
        else:
            band_data = image_array[band_idx]
        
        # 处理当前波段
        fixed_band = process_band_optimized(
            band_data, 
            band_idx, 
            band_count, 
            height, 
            width,
            chunk_size=chunk_size,
            buffer_size=buffer_size,
            missing_value=missing_value
        )
        
        # 存储修复后的波段
        fixed_image[band_idx] = fixed_band
        
        # 释放内存
        del band_data
        del fixed_band
        gc.collect()
    
    # 保存修复后的图像
    print("保存修复后的图像...")
    save_array_as_tiff(fixed_image, output_path)
    
    total_time = time.time() - start_time
    print(f"\n处理完成! 总耗时: {total_time/60:.2f}分钟")
    print(f"峰值内存使用: {memory_usage() - start_mem:.2f} MB")
    print(f"结果保存至: {output_path}")
    
    return output_path, fixed_image

def visualize_comparison_safe(original_path, fixed_path, band_index=0, sample_size=1000):
    """
    安全可视化修复前后的对比（避免加载整个大图像）
    """
    print(f"可视化波段 {band_index+1} 对比...")
    
    # 加载原始图像
    with Image.open(original_path) as orig_img:
        if orig_img.n_frames > 1:
            orig_img.seek(band_index)
        orig_band = np.array(orig_img)
    
    # 加载修复后的图像
    with Image.open(fixed_path) as fixed_img:
        if fixed_img.n_frames > 1:
            fixed_img.seek(band_index)
        fixed_band = np.array(fixed_img)
    
    # 创建对比图
    plt.figure(figsize=(16, 8))
    
    # 原始图像
    plt.subplot(121)
    plt.imshow(orig_band, cmap='viridis')
    plt.title(f'原始波段 {band_index+1}')
    plt.colorbar(label='像素值')
    
    # 修复后图像
    plt.subplot(122)
    plt.imshow(fixed_band, cmap='viridis')
    plt.title(f'修复后波段 {band_index+1}')
    plt.colorbar(label='像素值')
    
    plt.tight_layout()
    plt.savefig(f'band_{band_index+1}_comparison.png', dpi=150, bbox_inches='tight')
    plt.show()
    
    print("可视化完成!")

def extract_single_band_safe(input_path, band_index, output_path):
    """安全提取单个波段并保存（避免内存问题）"""
    print(f"提取波段 {band_index+1}...")
    
    with Image.open(input_path) as src_img:
        # 定位到指定波段
        if src_img.n_frames > 1:
            src_img.seek(band_index)
        
        # 直接保存该波段
        src_img.save(output_path)
    
    print(f"已提取波段 {band_index+1} 并保存至: {output_path}")

if __name__ == "__main__":
    # 配置路径
    input_tiff = r"D:\LE0712\B1.tif"
    output_tiff = r"D:\LE0712\fixed_landsat1.tif"
    single_band_output = r"D:\LE0712\fixed_band1.tif"
    
    # 检查内存
    print(f"初始内存使用: {memory_usage():.2f} MB")
    
    # 步骤1: 修复 TIFF (使用保守参数)
    output_path, fixed_image = fix_landsat7_tiff_optimized(
        input_tiff, 
        output_tiff,
        chunk_size=128,    # 更小的块大小
        buffer_size=16,    # 更小的缓冲区
        missing_value=0
    )
    
    # 步骤2: 安全可视化对比（波段4）
    visualize_comparison_safe(input_tiff, output_path, band_index=3)
    
    # 步骤3: 安全提取单个波段（波段4）
    extract_single_band_safe(output_path, 3, single_band_output)
    
    print("处理流程完成！")