# -*- coding: utf-8 -*-

"""
/***************************************************************************
Name                : PS Time Series Viewer
Description         : Computation and visualization of time series of speed for
                    Permanent Scatterers derived from satellite interferometry
Date                : Jul 25, 2012
copyright           : (C) 2012 by Giuseppe Sucameli (Faunalia)
email               : brush.tyler@gmail.com

 ***************************************************************************/

/***************************************************************************
 *                                                                         *s
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import re
from qgis.PyQt.QtCore import pyqtSignal, Qt, QObject, QRegExp, QDate
from qgis.PyQt.QtWidgets import QApplication, QWidget, QAction, QDockWidget,QMainWindow,QFileDialog,QDialog,QPushButton,QLabel,QTextEdit,QVBoxLayout,QMessageBox
from qgis.PyQt.QtGui import QIcon


from qgis.core import QgsFeature, QgsFeatureRequest, QgsMessageLog, QgsSettings,QgsGeometry,QgsVectorLayer,QgsVectorFileWriter,QgsPointXY,QgsPoint
from qgis.gui import QgsMapToolEmitPoint
import numpy as np
from matplotlib.dates import date2num

from .plot_wdg import PlotWdg, NavigationToolbar,PlotPS, PlotDlg
from . import resources_rc

from .graph_settings_dialog import GraphSettings_Dlg

from .ui.Ps_Time_Serie_Viewer_ui import Ui_Form

from .MapTools import FeatureFinder



class PSTimeSeries_Dlg(QDialog):

	featureChanged = pyqtSignal()

	def __init__(self, vl, fieldMap, parent=None):
		QDialog.__init__(self, parent=parent)
		self.setWindowTitle("PS Time Series Viewer")
		self._vl = vl
		self._fieldMap = fieldMap
		self._feat = None
		self.feat_list=[]
		self.vl_list=[]
		self.fieldMap_list=[]             
		self.plot = self.createPlot()
		self.nav = self.createToolBar()
		self.toolbar = ToolPSToolbar( self )  
		self.featureChanged.connect( self.toolbar.updateInfos )
		self.nav.updateRequested.connect( self.refresh )     
		self.toolbar.updateLimitsSig.connect( self.plot.setLimits )
		self.toolbar.updateReplicasSig.connect( self.plot.setReplicas )
		self.toolbar.updateGridsSig.connect( self.plot.displayGrids )
		self.toolbar.updateOptionsSig.connect( self.updateOptions )
		self.toolbar.updateLabelsSig.connect( self.plot.updateLabels )
		self.toolbar.updateTitleSig.connect( self.updateTitle )
		self.toolbar.init( self._fieldMap )
        
	def enterEvent(self, event):
		self.nav.set_cursor( NavigationToolbar.Cursor.POINTER )
		return QDialog.enterEvent(self, event)

	def leaveEvent(self, event):
		self.nav.unset_cursor()
		return QDialog.leaveEvent(self, event)
		
	def addLayer( self, vl, fieldMap,parent=None ):
		self.fieldMap_list.append(self._fieldMap)
		self._fieldMap=fieldMap
		self.vl_list.append(self._vl)
		self._vl = vl
	
	def addPlotPS(self,x,y):
		self.plotps=PlotPS(x,y)
		self.plot.collections.append(self.plotps)
	
	def createPlot(self):
		return PlotGraph()

	def createToolBar(self):
		return NavToolbar(self.plot, self)

	def addFeatureId(self,fid): #when some points are plotted
		feat = QgsFeature()
		feats = self._vl.getFeatures( QgsFeatureRequest(fid) )
		feats.nextFeature(feat)
		self._feat = feat
		self.feat_list.append(self._feat)
		# update toolbar widgets based on the new feature
		self.featureChanged.emit()

		return self._feat is not None

	def setFeatureId(self, fid):
		feat = QgsFeature()
		feats = self._vl.getFeatures( QgsFeatureRequest(fid) )
		feats.nextFeature(feat)
		self._feat = feat

		# update toolbar widgets based on the new feature
		self.featureChanged.emit()
        
		return self._feat is not None
	
	def showEvent(self, event):
		PlotDlg.showEvent(self, event)
		# update the graph data limits
		self.updateLimits( *self.plot.getLimits() )

	def hideEvent(self, event):
		QApplication.restoreOverrideCursor()
		PlotDlg.hideEvent(self, event)
		
	def refresh(self):
		self.plot._clear()                     
		lim = self.plot.getLimits()
		# change the plot colors/fonts
		self.plot.updateSettings()
		# refresh everything
		self.toolbar.updateAll()
		self.plot._plot()   #elem                      
		self.plot.setLimits( *lim )

	def updateOptions(self, options):
		""" update the chart options """
		self.plot.displayLines( options['lines'] )
		#self.plot.displayLegend( options['legend'] )
		self.plot.displaySmoothLines( options['smooth'] )
		self.plot.displayTrendLine( options['linregr'], 1 )
		self.plot.displayTrendLine( options['polyregr'], 3 )
		self.plot.displayDetrendedValues( options['detrending'] )

	def updateTitle(self, params):
		""" update the chart title """
		title = ""

		if self._feat:
			attrs = self._feat.attributes()

			# add the PS code
			for idx, fld in self._fieldMap.items():
				if not fld.name().lower().startswith( "code" ):
					continue
				title = "PS: %s" % attrs[ idx ]

			# add the user-defined values
			for label, fldIdx in params:
				title += " %s %s" % ( label, attrs[ fldIdx ] )

		self.plot.updateTitle( title )

	def updateLimits(self, xlim, ylim):
		self.toolbar.setLimits( xlim, ylim, True )

#------------------------------------------------------------------------------------------

class PlotGraph(PlotWdg):
	def __init__(self, *args, **kwargs):
		PlotWdg.__init__(self,	*args, **kwargs)
		self._showDetrendedValues = False
		self._origY = []
		self._points = []
		self._lines = []
		self._smoothLines = []
		self._trendLines = []
		self._upReplica = []
		self._downReplica = []
		self.updateSettings()

	def updateSettings(self):
		settingsToDict = GraphSettings_Dlg.settingsToDict
		settings = QgsSettings()

		self._pointsSettings = settingsToDict( settings.value("/pstimeseries/pointsProps", {'marker':'s', 'c':'k'}) )
		self._linesSettings = settingsToDict( settings.value("/pstimeseries/linesProps", {'c':'k'}) )
		self._trendLineSettings = settingsToDict( settings.value("/pstimeseries/linesThrendProps", {'c':'r'}) )
		self._upReplicaSettings = settingsToDict( settings.value("/pstimeseries/pointsReplicasProps", {'marker':'s', 'c':'b'}) )
		self._downReplicaSettings = settingsToDict( settings.value("/pstimeseries/pointsReplicasProps", {'marker':'s', 'c':'b'}) )
		self._titleSettings = settingsToDict( settings.value("/pstimeseries/titleProps", {'fontsize':'large'}) )
		self._labelsSettings = settingsToDict( settings.value("/pstimeseries/labelsProps", {'fontsize':'medium'}) )
		
	def _updateLists(self):
		self._origY.append(None)
		self._points.append(None)
		self._lines.append(None)
		self._smoothLines.append(None)
		self._trendLines.append({})
		self._upReplica.append(None)
		self._downReplica.append(None)
		
	def _updateListsMinus(self):
		self._origY.append(None)
		self._points.append(None)
		self._lines.append(None)
		self._smoothLines.append(None)
		self._trendLines.append({})
		self._upReplica.append(None)
		self._downReplica.append(None)
        
	def _plot(self):
		
		#remove and re-draw points
		for idx in range(len(self.collections)):
			if self._showDetrendedValues:
				self._origY[idx] = self.collections[idx].y
				self.collections[idx].y += -np.array( self._getTrendLineData(idx)[1] )
	
			elif self._origY[idx] is not None:
				self.collections[idx].y = self._origY[idx]
				self._origY = None
	
			# remove and re-draw points
			self._removeItem( self._points[idx],idx )     
			self._points[idx] = self._callPlotFunc('scatter', self.collections[idx].x, self.collections[idx].y, **self._pointsSettings)
			self.collections[idx].items.append(self._points[idx])
	
			# update lines related to the main plot
			self.displayLines( bool(self._lines[idx]) )
			for grade in self._trendLines[idx]:
				self.displayTrendLine( True, grade )
			self.displaySmoothLines( bool(self._smoothLines[idx]) )

	def displayLines(self, show=True): 
		for idx in range(len(self.collections)):
			# destroy the lines
			if self._lines[idx]:
				self._removeItem( self._lines[idx] ,idx)
				self._lines[idx] = None
	
			if show:
				lim = self.getLimits()
				self._lines[idx] = self._callPlotFunc('plot', self.collections[idx].x, self.collections[idx].y, **self._linesSettings)
				self.collections[idx].items.append( self._lines[idx] )
				self.setLimits( *lim )
	
		self.draw()

	def _getTrendLineData(self,idx, d=1):  
		x = date2num( np.array( self.collections[idx].x) )
		y = np.array( self.collections[idx].y)
		p = np.polyfit(x, y, d)
		return x, np.polyval(p, x)

	def displayTrendLine(self, show=True, grade=1):      
		for idx in range(len(self.collections)):
	# destroy the trend line
			if grade in self._trendLines[idx]:
				self._removeItem( self._trendLines[idx][grade],idx )
				del self._trendLines[idx][ grade ]
	
			if show:
				lim = self.getLimits()
				x, y = self._getTrendLineData( idx, grade )
				trendline = self._callPlotFunc('plot', x, y, **self._trendLineSettings)
				self.collections[idx].items.append( trendline )
				self._trendLines[idx][ grade ] = trendline
				self.setLimits( *lim )
	
			self.draw()

	def displayDetrendedValues(self, show):
		if self._showDetrendedValues == show:
			return

		self._showDetrendedValues = show
		self._plot()
		self.draw()

	def displaySmoothLines(self, show=True):
		for idx in range(len(self.collections)):
		# destroy the smooth line
			if self._smoothLines[idx]:
				self._removeItem( self._smoothLines[idx],idx )
				self._smoothLines[idx] = None
	
			if show:
				try:
					from scipy import interpolate
					x = date2num( np.array( self.collections[idx].x) )
					y = np.array( self.collections[idx].y)
	
					tck = interpolate.splrep(x,y)
					xmin, xmax = np.min(x), np.max(x)
					xnew = np.arange( xmin, xmax, float(xmax-xmin)/len(x)/20.0 )
					ynew = interpolate.splev(xnew, tck, der=0)
				except (ImportError, ValueError):
					return
	
				lim = self.getLimits()
				self._smoothLines[idx] = self._callPlotFunc('plot', xnew, ynew, **self._linesSettings)
				self.collections[idx].items.append( self._smoothLines[idx] )
				self.setLimits( *lim )
	
			self.draw()

	def updateTitle(self, title):
		self.setTitle(title, fontdict=self._titleSettings)

	def updateLabels(self, xLabel, yLabel):
		self.setLabels(xLabel, yLabel, fontdict=self._labelsSettings)

	def setReplicas(self, dist, positions):
		""" set up and/or down replicas for the graph """
		for idx in range(len(self.collections)):
			up, down = positions
	
			if self._upReplica[idx]:
				self._removeItem( self._upReplica[idx], idx )
				self._upReplica[idx] = None
	
			if up:
				y = list(map(lambda v: v+dist,  self.collections[idx].y))
				self._upReplica[idx] = self._callPlotFunc('scatter',  self.collections[idx].x, y, **self._upReplicaSettings)
				self.collections[idx].items.append( self._upReplica[idx] )
	
			if self._downReplica:
				self._removeItem( self._downReplica[idx],idx )
				self._downReplica[idx] = None
	
			if down:
				y = list(map(lambda v: v-dist, self.collections[idx].y))
				self._downReplica[idx] = self._callPlotFunc('scatter',  self.collections[idx].x, y, **self._downReplicaSettings)
				self.collections[idx].items.append( self._downReplica[idx] )
	
			self.draw()

#------------------------------------------------------------------------------------------

class MainPSWindow(QMainWindow): 
	click_ref=pyqtSignal(QgsPoint, Qt.MouseButton)
	close=pyqtSignal()

	def __init__(self,iface,parent=None):
		QMainWindow.__init__(self, parent=parent)
        
		# build ui
		self.ui=Ui_Form() #Appelle la fenêtre
		self.ui.setupUi(self) #Construit l'interface
		self.setCentralWidget(self.ui.PS_Time_Viewer) #Définit la fenêtre principal de l'interface
		self.first_point=True 
		
		# Set up the user interface from Designer.
		self.iface=iface 
		self.canvas=iface.mapCanvas() #Lie QGIS et la fenêtre
        
		# connect signals
		self.make_connection() #Relie les boutons aux actions
        
	def set_ps_layer(self, ps_layer):
		self.ps_layer = ps_layer
		
	def setupUi2(self,Form):
		"""Ajoutons ce qu'il manque à la fenêtre"""
		self.ui.setupUi(self, Form)
		Form.closeEvent = self.close_Event

	def closeEvent(self,event):
		result = QMessageBox.question(self,
					"Confirm Exit...",
					"Are you sure you want to exit ?",
					QMessageBox.Yes| QMessageBox.No)
		event.ignore()

		if result == QMessageBox.Yes:
			self.close.emit()
			event.accept()
			
	def addDlg(self,dlg):
		self.dlg=dlg
		self.ui.graph_loc.addWidget(self.dlg.toolbar,0,Qt.AlignTop)#gridLayout_21
		self.ui.graph_loc.addWidget(self.dlg.plot,40,Qt.AlignTop)#verticalLayout_2
		self.ui.graph_loc.addWidget(self.dlg.nav,2,Qt.AlignTop)#verticalLayout_2
    
	def get_diff(self,toSelect):
		x, y = [], []    # lists containg x,y values
		self.infoFields = {}    # hold the index->name of the fields containing info to be displayed
        
		fid = []
		x = []
		y = []
		if len(toSelect) == 2:
			for elem in toSelect:
				#self.ui.graph_loc.addWidget(self.dlg.plot,40,Qt.AlignTop)#verticalLayout_2
				idx = self.ui.list_series.row(elem)
				fid.append(int(str(elem.text()).split()[-1]))
				x.append(x)
				y.append(y)
				print("x", x)
				print("y", y)
				print("fid",fid)
		else:
			QMessageBox.information(self.iface.mainWindow(), " ", "Sélectionner 2 points", QMessageBox.Ok)
        
		ps_layer = self.iface.activeLayer()
		ps_fields = ps_layer.dataProvider().fields()
		print("ps_fields",ps_fields)
		feat = QgsFeature()
		#feats = ps_layer.getFeatures( QgsFeatureRequest(fid) )
		#feats.nextFeature(feat)
		attrs = feat.attributes()
# 		print("feat",feat)
# 		print("attrs",attrs)
		print(x,y)
        
		for idx, fld in enumerate(ps_fields):
			if QRegExp( "D\\d{8}", Qt.CaseInsensitive ).indexIn( fld.name() ) < 0:
                # info fields are all except those containing dates
				self.infoFields[ idx ] = fld
			else:
				coor = []
				for i in len(fid):
					for j in len(ps_fields):
						coor.append(self.plotps)
# 						x.append( QDate.fromString( fld.name()[1:], "yyyyMMdd" ).toPyDate() )
						print("coor", coor)
						iterator = ps_layer.getFeatures(QgsFeatureRequest().setFilterFid(fid))
						feature = next(iterator)
# 						y.append( float(attrs[ idx ]) )
# 						print("y", y)
                
		QMessageBox.information(self.iface.mainWindow(), " ", "Hourra", QMessageBox.Ok)
    
		return x, y
    
	def plot_diff(self) :
		self.nb_series=0
		toSelect = self.ui.list_series.selectedItems()
		print(toSelect)
		Selected = self.get_diff( toSelect )

		try:
			if self.x[0] == self.x[1]:
				xdiff = self.x[0]
				ydiff = self.y[0] - self.y[1]
                
				if self.nb_series==0 or self.first_point==True:
					self.dlg = PSTimeSeries_Dlg( self.ps_layer, self.infoFields )
					self.dlg.plot.setData( xdiff, ydiff )
					self.dlg.addPlotPS( xdiff, ydiff )
					self.dlg.plot._updateLists()
					self.window.addDlg( self.dlg )
					self.nb_series+=1
					self.first_point=False
                
				else:
					self.window.dlg.addLayer( self.ps_layer, self.infoFields )                          
					self.window.dlg.plot.setData( xdiff, ydiff )    
					self.window.dlg.addPlotPS( xdiff, ydiff )   
					self.window.dlg.plot._updateLists() 
					self.window.dlg.refresh()                           
					self.nb_series+=1
			else:
				QMessageBox.warning( self.iface.mainWindow(),"PS Time Series Viewer","No match in time." % self.ts_tablename )

			return xdiff, ydiff
            
		except:
			QMessageBox.information(self.iface.mainWindow(), " ", "Whoops", QMessageBox.Ok)

	##### Buttons#####################################################################################################
		
	def search_time_series(self):
		self.dlg_files = QFileDialog()
		directory = QFileDialog.getOpenFileName(None, "Select a directory", "","Shapefile (*.shp)")#,
		QgsMessageLog.logMessage(str(directory))
		if not(directory == ""):
			self.ui.time_series.setText(directory[0]) 
			print("ok")
		else:
			print("")
			
	def search_metadata(self):
		self.dlg_files = QFileDialog()
		directory = QFileDialog.getOpenFileName(None, "Select a directory", "","CSV (*.csv)")#,
		QgsMessageLog.logMessage(str(directory))
		if not(directory == ""):
			self.ui.metadata.setText(directory[0]) 
			print("ok")
		else:
			print("")
			
	def search_gnss(self):
		self.dlg_files = QFileDialog()
		directory = QFileDialog.getOpenFileName(None, "Select a directory", "","CSV (*.csv)")#,
		QgsMessageLog.logMessage(str(directory))
		if not(directory == ""):
			self.ui.gnss_2.setText(directory[0]) 
			print("ok")
		else:
			print("")
			
	def search_ref(self):
		self.dlg_files = QFileDialog()
		directory = QFileDialog.getOpenFileName(None, "Select a directory", "","Shapefile (*.shp)")#,
		QgsMessageLog.logMessage(str(directory))
		if not(directory == ""):
			self.ui.ref_2.setText(directory[0]) 
			print("ok")
		else:
			print("")
	
	def load_time_series(self):
		self.ui.layers_for_options.addItem(self.ui.time_series.toPlainText())
		self.ui.list_series.addItem(self.ui.time_series.toPlainText())
		self.ui.list_time_series_with_new_ref.addItem(self.ui.time_series.toPlainText())
		
	def load_gnss(self):
		self.ui.gnss_selection_list.addItem(self.ui.gnss_2.toPlainText())
		
	def load_ref(self):
		self.ui.ref_list.addItem(self.ui.ref_2.toPlainText())
		layer = self.iface.addVectorLayer(self.ui.ref_2.toPlainText(), "ref", "ogr")
		if not layer:
			print("Layer failed to load!")
		click_ref=pyqtSignal(QgsPoint, Qt.MouseButton)
        
	def remove_ts(self):
		toRemove=self.ui.list_series.selectedItems()
		if toRemove!=[]:
			#QgsMessageLog.logMessage("Items selectionnés mais pas supprimés")
			for elem in toRemove:
				idx=self.ui.list_series.row(elem)
				self.ui.layers_for_options.takeItem(idx)
				self.ui.list_series.takeItem(idx)
				self.ui.list_time_series_with_new_ref.takeItem(idx)
				self.dlg.plot._removeCollection( self.dlg.plot.collections[idx] )  
				self.dlg.refresh()
				QgsMessageLog.logMessage(str(idx)+"   "+str(len(toRemove)))
	
	def new_ref(self):   
		self.dlg_ref = QFileDialog()
		directory = QFileDialog.getExistingDirectory(None, 'Select a folder:', '', QFileDialog.ShowDirsOnly)
		
		QgsMessageLog.logMessage(str(directory))
		if not(directory == ""):
			self.ui.create_new_ref.setText(directory) 
			print("ok")
		else:
			print("")
		# layer = iface.addVectorLayer(self.ui.create_new_ref.toPlainText(), "ref", "ogr")
		# if not layer:
		# 	print("Layer failed to load!")
	
	#run method that performs all the real work
	def create_new_ref(self):
		self.point=None
		self.w = QWidget()
		self.w.resize(250, 150)
		self.w.move(300, 300)
		self.w.setWindowTitle('New Reference Area')
		self.label = QLabel(self.tr(u'Set a radius value'))
		self.TextEdit = QTextEdit()
		self.label2 = QLabel(self.tr(u'Click on the QGIS interface to set area s center'))
		self.TextEdit2 = QTextEdit()
		self.btn = QPushButton('Ok', self.w)
		self.vbox = QVBoxLayout(self.w)
		self.vbox.addWidget(self.label)
		self.vbox.addWidget(self.TextEdit)
		self.vbox.addWidget(self.label2)
		self.vbox.addWidget(self.TextEdit2)
		self.vbox.addWidget(self.btn)
		self.w.setLayout(self.vbox) 
		self.w.show()
		self.canvas = self.iface.mapCanvas()
        
		# out click tool will emit a QgsPoint on every click
		self.clickTool = QgsMapToolEmitPoint(self.canvas)
        
		# create our GUI dialog
		self.clickTool.canvasClicked.connect(self.handleMouseDown)
		self.btn.clicked.connect(self.draw_ref)	
		self.canvas.setMapTool(self.clickTool)
		
	def handleMouseDown(self, point, button):
		self.point=point
		self.TextEdit2.setText(str(point.x()) + " , " +str(point.y()))
		
	def draw_ref(self):
		QMessageBox.information(self.iface.mainWindow(), "PS Time Series Viewer", "Ok")
		try:
			self.radius=float(self.TextEdit.toPlainText())
		except:
			QMessageBox.information(self.iface.mainWindow(), "PS Time Series Viewer", "Please set a float")
		
		if self.point:
			pathText=self.ui.create_new_ref.toPlainText()
			if pathText=="":
				pathText="D:"
			path=pathText+"/reference_area.shp"
			uri = path + "|referenceArea"
			vpoly = QgsVectorLayer(uri, 'referenceArea', "ogr")#
			feature = QgsFeature()
			feature.setGeometry( QgsGeometry.fromPointXY(self.point).buffer(self.radius,100))
			provider = vpoly.dataProvider()
			vpoly.startEditing()
			provider.addFeatures( [feature] )
			vpoly.commitChanges()
		else:
			QMessageBox.information(self.iface.mainWindow(), "PS Time Series Viewer", "No point ")
	
		#QMessageBox.information( self.iface.mainWindow(),"Info", "X,Y = %s,%s" % (str(point.x()),str(point.y())) )
		
	# def plot_legend(self):
	# 	path=self.ui.layers_for_options.selectedItems()
	# 	myVectorLayer = QgsVectorLayer(path+"|layer", "layer", 'ogr')
	# 	myTargetField = 'target_field'
	# 	myRangeList = []
	# 	myOpacity = 1
	# 	# Make our first symbol and range...
	# 	myMin = 0.0
	# 	myMax = 50.0
	# 	myLabel = 'Group 1'
	# 	myColour = QtGui.QColor('#ffee00')
	# 	mySymbol1 = QgsSymbol.defaultSymbol(myVectorLayer.geometryType())
	# 	mySymbol1.setColor(myColour)
	# 	mySymbol1.setOpacity(myOpacity)
	# 	myRange1 = QgsRendererRange(myMin, myMax, mySymbol1, myLabel)
	# 	myRangeList.append(myRange1)
	# 	#now make another symbol and range...
	# 	myMin = 50.1
	# 	myMax = 100
	# 	myLabel = 'Group 2'
	# 	myColour = QtGui.QColor('#00eeff')
	# 	mySymbol2 = QgsSymbol.defaultSymbol(
	# 		myVectorLayer.geometryType())
	# 	mySymbol2.setColor(myColour)
	# 	mySymbol2.setOpacity(myOpacity)
	# 	myRange2 = QgsRendererRange(myMin, myMax, mySymbol2, myLabel)
	# 	myRangeList.append(myRange2)
	# 	myRenderer = QgsGraduatedSymbolRenderer('', myRangeList)
	# 	myRenderer.setMode(QgsGraduatedSymbolRenderer.EqualInterval)
	# 	myRenderer.setClassAttribute(myTargetField)
	# 	
	# 	myVectorLayer.setRenderer(myRenderer)
	# 	QgsProject.instance().addMapLayer(myVectorLayer)
	# 	for legendLyr in self.iface.mapCanvas().layers():
	# 		if legendLyr.name() != "os1250_line" and legendLyr.name() != "os1250_text":
	# 			renderer = legendLyr.rendererV2()
	# 			if renderer.type() == "categorizedSymbol":
	# 				myRenderer = renderer.clone()
	# 				idx=0
	# 				for cat in myRenderer.categories():
	# 					myRenderer.updateCategoryLabel (idx,"foo")
	# 					idx+=1      
	# 				legendLyr.setRendererV2(myRenderer)
	# 				legendLyr.triggerRepaint()
		
			
#######################################################################################################################	
		
	def make_connection(self):
		"""
		Create connection for window item
		"""
		
		#searching file for loading
		self.ui.time_series_search.clicked.connect(self.search_time_series)#(self.ui.time_series)
		self.ui.gnss_search.clicked.connect(self.search_gnss)
		self.ui.ref_search.clicked.connect(self.search_ref)
		
		#pushing files
		self.ui.time_series_push.clicked.connect(self.load_time_series)
		self.ui.gnss_push.clicked.connect(self.load_gnss)
		self.ui.ref_push.clicked.connect(self.load_ref)
		self.ui.remove_push.clicked.connect(self.remove_ts)
		self.ui.plot_difference.clicked.connect(self.plot_diff)
		self.ui.new_ref.clicked.connect(self.new_ref)
		self.ui.create_new_ref_push.clicked.connect(self.create_new_ref)
		#self.ui.params_ok.clicked.connect(self.plot_legend)
		
		
from .ui.tool_ps_toolbar_ui import Ui_ToolPSToolBar

class ToolPSToolbar(QWidget, Ui_ToolPSToolBar):
	updateGridsSig = pyqtSignal(bool, bool)
	updateReplicasSig = pyqtSignal(float, tuple)
	updateOptionsSig = pyqtSignal(dict)
	updateLimitsSig = pyqtSignal(tuple, tuple)
	updateLabelsSig = pyqtSignal(str, str)
	updateTitleSig = pyqtSignal(list)

	def __init__(self, parent=None):
		QWidget.__init__(self, parent)
		self.setupUi(self)
		self.legendCheck.hide()
		self.smoothCheck.hide()
		self.refreshScaleButton.setIcon( QIcon( ":/pstimeseries_plugin/icons/refresh" ) )

		# limits group
		#self.connect(self.minDateEdit, SIGNAL("dateChanged(const QDate &)"), self.updateLimits)
		#self.connect(self.maxDateEdit, SIGNAL("dateChanged(const QDate &)"), self.updateLimits)
		#self.connect(self.minYEdit, SIGNAL("valueChanged(const QString &)"), self.updateLimits)
		#self.connect(self.minYEdit, SIGNAL("valueChanged(const QString &)"), self.updateLimits)
		self.refreshScaleButton.clicked.connect(self.updateLimits)

		# replica group
		self.replicaUpCheck.toggled.connect(self.updateReplicas)
		self.replicaDownCheck.toggled.connect(self.updateReplicas)
		self.replicaDistEdit.textChanged.connect(self.updateReplicas)

		# labels group
		self.xLabelEdit.textChanged.connect(self.updateLabels)
		self.yLabelEdit.textChanged.connect(self.updateLabels)

		# title group
		for i in range(3):
			edit = getattr(self, "titleParam%dEdit" % i)
			edit.textChanged.connect(self.updateTitle)
			combo = getattr(self, "titleParam%dCombo" % i)
			combo.currentIndexChanged.connect(self.updateTitle)

		# options group
		self.hGridCheck.toggled.connect(self.updateGrids)
		self.vGridCheck.toggled.connect(self.updateGrids)
		self.labelsCheck.toggled.connect(self.updateLabels)
		self.linesCheck.toggled.connect(self.updateOptions)
		self.linRegrCheck.toggled.connect(self.updateOptions)
		self.polyRegrCheck.toggled.connect(self.updateOptions)
		self.detrendingCheck.toggled.connect(self.updateOptions)
		self.smoothCheck.toggled.connect(self.updateOptions)
		self.legendCheck.toggled.connect(self.updateOptions)

	def init(self, fieldMap):
		self.populateTitleParamCombos( fieldMap )
		self.labelsCheck.setChecked( True )

	def updateAll(self):
		self.updateTitle()
		self.updateLabels()
		self.updateReplicas()
		self.updateOptions()

	def updateInfos(self):
		self.updateTitle()

	def populateTitleParamCombos(self, fieldMap):
		""" populate the title param combos """
		for i in range(3):
			edit = getattr(self, "titleParam%dEdit" % i)
			combo = getattr(self, "titleParam%dCombo" % i)
			# populate the title param combo with fields
			for fldIdx, fld in fieldMap.items():
				combo.addItem( fld.name(), fldIdx )
				if bool( re.match("^"+edit.text()[:-2], fld.name(), re.IGNORECASE )):
					combo.setCurrentIndex( combo.count()-1 )

	def updateReplicas(self):
		""" request the graph replicas updating """
		try:
			dist = float(self.replicaDistEdit.text())
		except:
			return
		upReplica = self.replicaUpCheck.isChecked()
		downReplica = self.replicaDownCheck.isChecked()
		self.updateReplicasSig.emit(dist, (upReplica, downReplica) )

	def updateGrids(self):
		""" request the chart grids updating """
		hgrid = self.hGridCheck.isChecked()
		vgrid = self.vGridCheck.isChecked()
		self.updateGridsSig.emit( hgrid, vgrid )

	def updateOptions(self):
		""" request the chart options updating """
		options = {
			'lines': self.linesCheck.isChecked(),
			'smooth': self.smoothCheck.isChecked(),
			'linregr': self.linRegrCheck.isChecked(),
			'polyregr': self.polyRegrCheck.isChecked(),
			'detrending': self.detrendingCheck.isChecked(),
			'legend': self.legendCheck.isChecked(),
		}

		self.updateOptionsSig.emit( options )

	def setLimits(self, xlim, ylim, update=False):
		self.minDateEdit.setDate(xlim[0])
		self.maxDateEdit.setDate(xlim[1])
		self.minYEdit.setText("%s" % ylim[0])
		self.maxYEdit.setText("%s" % ylim[1])
		if update:
			self.updateLimits()

	def updateLimits(self):
		""" request the chart axis limits updating """
		xLimits = (self.minDateEdit.date().toPyDate(), self.maxDateEdit.date().toPyDate())
		yLimits = (float(self.minYEdit.text()), float(self.maxYEdit.text()))
		self.updateLimitsSig.emit( xLimits, yLimits )

	def updateLabels(self):
		""" request the chart axis labels updating """
		if self.labelsCheck.isChecked():
			xLabel = self.xLabelEdit.text()
			yLabel = self.yLabelEdit.text()
		else:
			xLabel = None
			yLabel = None
		self.updateLabelsSig.emit( xLabel, yLabel )

	def updateTitle(self):
		""" request the chart title updating """
		params = []

		for i in range(3):
			# get param label
			label = getattr(self, "titleParam%dEdit" % i).text()
			# get param value
			combo = getattr(self, "titleParam%dCombo" % i)
			#print "combo", combo, combo.currentIndex(),
			fldIdx = combo.itemData( combo.currentIndex() )
			params.append( (label, fldIdx) )

		self.updateTitleSig.emit( params)

#------------------------------------------------------------------------------------------

class NavToolbar(NavigationToolbar):
	updateRequested = pyqtSignal()

	def __init__(self, canvas, parent=None):
		NavigationToolbar.__init__(self, canvas, parent)

		# add toolbutton to change fonts/colors
		self.fontColorAction = QAction( QIcon(":/pstimeseries_plugin/icons/settings"), "Change fonts and colors", self )
		self.fontColorAction.setToolTip( "Change fonts and colors" )
		self.insertAction(self.homeAction, self.fontColorAction)
		self.fontColorAction.triggered.connect(self.openFontColorSettings)
		self.insertSeparator(self.homeAction)

	def openFontColorSettings(self):
		dlg = GraphSettings_Dlg(self)
		if dlg.exec_():
			self.updateRequested.emit()

