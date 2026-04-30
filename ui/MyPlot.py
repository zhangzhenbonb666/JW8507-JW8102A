#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实时曲线绘图模块

本模块提供了一个基于pyqtgraph的实时数据曲线绘图组件。
用于显示功率值随时间变化的曲线图。

主要功能:
    - 实时数据追加和显示
    - 多数据序列支持
    - 双击切换数据序列
    - 自动范围调整
    - 数据清除

类:
    MyPlot: 实时曲线绑图控件

使用示例:
    >>> plot = MyPlot({'功率': [0]})
    >>> layout.addWidget(plot)
    >>> plot.update_signal.emit({'功率': -15.5})  # 添加新数据点
"""

import numpy as np
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtWidgets import QFileDialog
import os

# pyqtgraph全局配置：白底黑线
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')


class MyPlot(pg.GraphicsLayoutWidget):
    """
    实时曲线绑图控件
    
    继承自pyqtgraph的GraphicsLayoutWidget，支持实时数据更新和多序列切换。
    
    信号:
        update_signal: 数据更新信号，参数为{序列名: 新数据值}
        
    属性:
        dataDict: 数据字典，{序列名: numpy数组}
        posDict: 位置偏移字典
        NowPlotNo: 当前显示的数据序列索引
    """
    
    dataDict = {}      # 数据存储字典
    posDict = {}       # 位置偏移字典
    NowPlotNo = 0      # 当前显示序列索引
    update_signal = pyqtSignal(dict)  # 数据更新信号

    def __init__(self, dataDict, dataLen=30):
        """
        初始化绑图控件
        
        Args:
            dataDict: 初始数据字典，格式为{序列名: 初始数据列表}
            dataLen: 保留参数（未使用）
        """
        super(MyPlot, self).__init__()
        self.dataDict = dataDict

        # self.dataLen = dataLen
        for k, v in dataDict.items():
            self.posDict[k] = 0
            if type(v) == list:
                self.dataDict[k] = np.array(v)
            elif type(v) == np.ndarray:
                self.dataDict[k] = v

        self.plot1 = self.addPlot()
        key = list(self.dataDict.keys())[self.NowPlotNo]
        self.plot1.setTitle(key, **{"font-family": "微软雅黑", 'font-size': '12pt'})
        self.update_signal.connect(self.updateData)
        self.curve = self.plot1.plot(self.dataDict[key], pen=pg.mkPen({'color': (0, 0, 255), 'width': 4}))

        pass

    def mousePressEvent(self, ev):
        return

    def mouseDoubleClickEvent(self, ev):
        self.NowPlotNo = (self.NowPlotNo + 1) % len(self.dataDict)
        key = list(self.dataDict.keys())[self.NowPlotNo]
        self.plot1.setTitle(key, **{"font-family": "微软雅黑", 'font-size': '20pt'})

        data1 = self.dataDict[key]
        self.curve.setData(data1)
        self.posDict[key] = 0
        self.curve.setPos(self.posDict[key], 0)

    def updateData(self, dataAddDict):
        for k, v in dataAddDict.items():
            # if len(self.dataDict[k]) < self.dataLen:
            self.dataDict[k] = np.append(self.dataDict[k], v)
            # else:
            #     self.dataDict[k][:-1] = self.dataDict[k][1:]
            #     self.dataDict[k][-1] = v
            #     self.posDict[k] += 1

        key = list(self.dataDict.keys())[self.NowPlotNo]
        data1 = self.dataDict[key]
        self.curve.setData(data1)
        self.curve.setPos(self.posDict[key], 0)
        self.plot1.autoRange()

    def clearData(self):
        for k, v in self.dataDict.items():
            self.dataDict[k] = np.array([])
            self.posDict[k] = 0
        key = list(self.dataDict.keys())[self.NowPlotNo]
        self.curve.setData(self.dataDict[key])
        self.curve.setPos(self.posDict[key], 0)
        self.plot1.autoRange()

    def save_image(self, filename=None, width=800, height=600):
        """
        保存当前折线图为图片
        
        Args:
            filename: 保存的文件路径。如果为None，则弹出文件保存对话框
            width: 图片宽度（像素），默认800
            height: 图片高度（像素），默认600
            
        Returns:
            bool: 保存成功返回True，失败或取消返回False
        """
        try:
            # 如果没有指定文件名，弹出保存对话框
            if filename is None:
                key = list(self.dataDict.keys())[self.NowPlotNo]
                default_filename = f"{key}_plot.png"
                filename, _ = QFileDialog.getSaveFileName(
                    self,
                    "保存图片",
                    default_filename,
                    "PNG图片 (*.png);;JPEG图片 (*.jpg *.jpeg);;所有文件 (*.*)"
                )
                
                # 用户取消保存
                if not filename:
                    return False
            
            # 创建导出器
            exporter = ImageExporter(self.plot1)
            
            # 设置导出参数
            exporter.parameters()['width'] = width
            exporter.parameters()['height'] = height
            
            # 导出图片
            exporter.export(filename)
            
            return True
            
        except Exception as e:
            print(f"保存图片失败: {e}")
            return False


if __name__ == '__main__':
    import sys
    import time
    from PyQt5.QtWidgets import QApplication
    from PyQt5 import QtCore, QtGui, QtWidgets

    app = QApplication(sys.argv)
    win = QtWidgets.QMainWindow()
    win.resize(800, 600)
    win.setWindowTitle('MyPlot')
    central_widget = QtWidgets.QWidget(win)
    layout = QtWidgets.QHBoxLayout(central_widget)
    plot = MyPlot({'A': [1, 2, 3, 4, 5], 'B': [2, 3, 4, 5, 6]})
    layout.addWidget(plot)
    win.setCentralWidget(central_widget)
    win.show()
    time.sleep(5)
    plot.updateData({'A': [6, 7, 8, 9, 10], 'B': [3, 4, 5, 6, 7]})
    time.sleep(10)
    plot.clearData()
    sys.exit(app.exec_())
