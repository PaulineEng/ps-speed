# -*- coding: utf-8 -*-
"""
Created on Fri Jan 10 09:36:47 2020

@author: Hugo Bontempi
"""

"""
/***************************************************************************
Name                : PS Time Series Viewer
Description         : Computation and visualization of time series of speed for
                    Permanent Scatterers derived from satellite interferometry
Date                : Jan 10, 2020
copyright           : (C) 2020 by Hugo Bontempi (ENSG)
email               : hugo.bontempi@ensg.eu

 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""



from PyQt5.QtCore import *
from PyQt5.QtGui import *
from qgis.core import *
from qgis.gui import *
import math
import numpy as np


#from myplugin_form import Ui_MypluginDockWidgetBase
from .ui.myplugin_form import Ui_MyPluginDockWidgetBase


class Download_Dlg(QDockWidget, Ui_MyPluginDockWidgetBase):
	""" My widget """
	
	closingPlugin = pyqtSignal()

	def __init__(self,iface,refmnt,refloc):
		QDockWidget.__init__(self)

		# Set up the user interface from Designer.
		self.setupUi(self)
		self.iface=iface
		self.canvas=iface.mapCanvas()

	# here I code.

	def closeEvent(self, event):
		self.cleanCanvas(canvasbool=True)
		self.closingPlugin.emit()
		event.accept()



