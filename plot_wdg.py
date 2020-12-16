# -*- coding: utf-8 -*-

"""
/****************************************************************************
Name			 	: GEM Modellers Toolkit plugin (GEM-MT)
Description			: Analysing and Processing Earthquake Catalogue Data
Date				: Jun 21, 2012
copyright			: (C) 2012 by Giuseppe Sucameli (Faunalia)
email				: brush.tyler@gmail.com
 ****************************************************************************/

/****************************************************************************
 *																			*
 *	This program is free software; you can redistribute it and/or modify	*
 *	it under the terms of the GNU General Public License as published by	*
 *	the Free Software Foundation; either version 2 of the License, or		*
 *	(at your option) any later version.										*
 *																			*
 ****************************************************************************/
"""
from qgis.core import QgsMessageLog
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QApplication, QSizePolicy
from qgis.PyQt.QtCore import Qt, QVariant
from qgis.PyQt.QtGui import QCursor

# Matplotlib Figure object
from matplotlib.figure import Figure

from datetime import datetime, date
from matplotlib.dates import date2num, num2date, YearLocator, MonthLocator, DayLocator, DateFormatter
from matplotlib.lines import Line2D

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg


class PlotPS():
	"""Class that define a PS Time"""
	def __init__(self, x, y=None):
		self.items=[]
		self.x=x
		self.y=y
		self._trendLines = {}

	def setData(self, x, y=None, info=None):
		self.x = x if x is not None else []
		self.y = y if y is not None else []
		self.info = info if info is not None else []   


class PlotWdg(FigureCanvasQTAgg):
	"""Class to represent the FigureCanvas widget"""
	def __init__(self, data=None, labels=None, title=None, props=None):

		self.fig = Figure()
		self.axes = self.fig.add_subplot(111)

		# initialize the canvas where the Figure renders into
		FigureCanvasQTAgg.__init__(self, self.fig)
		FigureCanvasQTAgg.setSizePolicy(self,QSizePolicy.Expanding,QSizePolicy.Expanding)
		self.resize(20, 10)
        
		self._dirty = False
		self.collections = []

		if not data: data = [None]
		self.setData( *data )

		if not labels: labels = [None]
		self.setLabels( *labels )

		self.setTitle( title )

		self.props = props if isinstance(props, dict) else {}

		yscale = self.props.get('yscale', None)
		if yscale:
			self.axes.set_yscale( yscale )
            
		#FigureCanvasQTAgg.updateGeometry(self)
        

	def itemAt(self, index,icollections):     #for each PlotPS object
		if index >= len(self.collections[icollections].x):
			return None
		return (self.collections[icollections].x[index] if self.collections[icollections].x else None, self.collections[icollections].y[index] if self.collections[icollections].y else None)

	def delete(self):
		self._clear()

		# unset delete function
		self.delete = lambda: None

	def __del__(self):
		self.delete()

	def deleteLater(self, *args):
		self.delete()
		return FigureCanvasQTAgg.deleteLater(self, *args)

	def destroy(self, *args):
		self.delete()
		return FigureCanvasQTAgg.destroy(self, *args)

	def setDirty(self, val):
		self._dirty = val

	def showEvent(self, event):
		if self._dirty:
			self.refreshData()
		return FigureCanvasQTAgg.showEvent(self, event)

	def refreshData(self):
		# remove the old stuff
		self._clear()
		# plot the new data
		self._plot()
		# update axis limits
		self.axes.relim()	# it doesn't shrink until removing all the objects on the axis
		# re-draw
		self.draw()
		# unset the dirty flag
		self._dirty = False

	def setData(self, x, y=None, info=None):
		self.x0 = x if x is not None else []
		self.y0 = y if y is not None else []
		self.info = info if info is not None else []
		self._dirty = True

	def getTitle(self):
		return self.axes.get_title()

	def setTitle(self, title, *args, **kwargs):
		self.axes.set_title( title or "", *args, **kwargs )
		self.draw()

	def getLabels(self):
		return self.axes.get_xlabel(), self.axes.get_ylabel()

	def setLabels(self, xLabel=None, yLabel=None, *args, **kwargs):
		self.axes.set_xlabel( xLabel or "", *args, **kwargs )
		self.axes.set_ylabel( yLabel or "", *args, **kwargs )
		self.draw()

	def getLimits(self):   #xlim et ylim globalisées
		idx=-1
		self.xlim = self.axes.get_xlim()
		is_x_date = isinstance((self.x0)[0], (datetime, date)) if len(self.x0) > 0 else False
		if is_x_date:

			self.xlim = num2date(self.xlim)
		self.ylim = self.axes.get_ylim()
		is_y_date = isinstance(self.y0[0], (datetime, date)) if self.y0 is not None and len(self.y0) > 0 else False
		if is_y_date:
			self.ylim = num2date(self.ylim)

		return self.xlim, self.ylim

	def setLimits(self, xlim=None, ylim=None):
		""" update the chart limits """
		if xlim is not None:
			self.axes.set_xlim(xlim)
		if ylim is not None:
			self.axes.set_ylim(ylim)
		self.draw()

	def displayGrids(self, hgrid=False, vgrid=False):
		self.axes.xaxis.grid(vgrid, 'major')
		self.axes.yaxis.grid(hgrid, 'major')
		self.draw()

	def _removeCollection(self, item):  #new
		try:
			self.collections.remove( item )
		except ValueError:
			QgsMessageLog.logMessage( "Collection not removed" )
			pass

	def _removeItem(self, item,idx):
		try:
			self.collections[idx].items.remove(item)
		except (ValueError, AttributeError):
			pass

	def _clear(self):
		for item in self.collections:

			item.items=[]

	def _plot(self):
		for idx in range(len(self.collections)):
			# convert values, then create the plot
			x = map(PlotWdg._valueFromQVariant, self.collections[idx].x)
			y = map(PlotWdg._valueFromQVariant, self.collections[idx].y)

			items = self._callPlotFunc('plot', x, y)
			self.collections[idx].items=items

	def _callPlotFunc(self, plotfunc, x, y=None, *args, **kwargs):
		is_x_date = isinstance(x[0], (datetime, date)) if len(x) > 0 else False
		is_y_date = isinstance(y[0], (datetime, date)) if y is not None and len(y) > 0 else False

		if is_x_date:
			self._setAxisDateFormatter( self.axes.xaxis, x )
			x = date2num(x)
		if is_y_date:
			self._setAxisDateFormatter( self.axes.yaxis, y )
			y = date2num(y)

		if y is not None:
			items = getattr(self.axes, plotfunc)(x, y, *args, **kwargs)
		else:
			items = getattr(self.axes, plotfunc)(x, *args, **kwargs)

		if is_x_date:
			self.fig.autofmt_xdate()
		#if is_y_date:
		#	self.fig.autofmt_ydate()

		return items

	@classmethod
	def _setAxisDateFormatter(self, axis, data):
		timedelta = max(data) - min(data)
		if timedelta.days > 365*5:
			axis.set_major_formatter( DateFormatter('%Y') )
			#axis.set_major_locator( YearLocator() )
			#axis.set_minor_locator( MonthLocator() )
			#bins = timedelta.days * 4 / 356	# four bins for a year

		elif timedelta.days > 30*5:
			axis.set_major_formatter( DateFormatter('%Y-%m') )
			#axis.set_major_locator( MonthLocator() )
			#axis.set_minor_locator( DayLocator() )
			#bins = timedelta.days * 4 / 30	# four bins for a month

		else:
			axis.set_major_formatter( DateFormatter('%Y-%m-%d') )
			#axis.set_major_locator( DayLocator() )
			#axis.set_minor_locator( HourLocator() )
			#bins = timedelta.days * 4	# four bins for a day

	@staticmethod
	def _valueFromQVariant(val):
		""" function to convert values to proper types """
		if not isinstance(val, QVariant):
			return val

		if val.type() == QVariant.Int:
			return int(val)
		elif val.type() == QVariant.Double:
			return float(val)
		elif val.type() == QVariant.Date:
			return val.toDate().toPyDate()
		elif val.type() == QVariant.DateTime:
			return val.toDateTime().toPyDateTime()

		# try to convert the value to a date
		s = str(val)
		try:
			return datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
		except ValueError:
			pass
		try:
			return datetime.strptime(s, '%Y-%m-%d')
		except ValueError:
			pass

		v, ok = val
		if ok: return v
		v, ok = val
		if ok: return v
		v = val.toDateTime()
		if v.isValid(): return v.toPyDateTime()
		v = val.toDate()
		if v.isValid(): return v.toPyDate()

		return str(s)


class HistogramPlotWdg(PlotWdg):
	def __init__(self, *args, **kwargs):
		PlotWdg.__init__(self, *args, **kwargs)

	def _plot(self):
		for idx in range(len(self.collections)):
			# convert values, then create the plot
			x = map(PlotWdg._valueFromQVariant, self.collections[idx].x)
			items = self._callPlotFunc('hist', x, bins=50)
			self.collections[idx].items = items


class ScatterPlotWdg(PlotWdg):
	def __init__(self, *args, **kwargs):
		PlotWdg.__init__(self, *args, **kwargs)

	def _plot(self):
		for idx in range(len(self.collections)):
			# convert values, then create the plot
			x = map(PlotWdg._valueFromQVariant, self.collections[idx].x)
			y = map(PlotWdg._valueFromQVariant, self.collections[idx].y)
			items = self._callPlotFunc('scatter', x, y)
			self.collections[idx].items = items


class PlotDlg(QDialog):
	def __init__(self, parent, *args, **kwargs):
		QDialog.__init__(self, parent, Qt.Window)
		self.setWindowTitle("Plot dialog")
		layout = QVBoxLayout(self)
		self.plot = self.createPlot(*args, **kwargs)
		layout.addWidget(self.plot)
		self.nav = self.createToolBar()
		layout.addWidget(self.nav)

	def enterEvent(self, event):
		self.nav.set_cursor( NavigationToolbar.Cursor.POINTER )
		return QDialog.enterEvent(self, event)

	def leaveEvent(self, event):
		self.nav.unset_cursor()
		return QDialog.leaveEvent(self, event)

	def createPlot(self, *args, **kwargs):
		return PlotWdg(*args, **kwargs)

	def createToolBar(self):
		return NavigationToolbar(self.plot, self)

	def refresh(self):
		# query for refresh
		self.plot.setDirty(True)
		if self.isVisible():
			# refresh if it's already visible
			self.plot.refreshData()

	def setData(self, x, y=None, info=None):
		self.plot.setData(x, y, info)

	def setTitle(self, title):
		self.plot.setTitle(title)

	def setLabels(self, xLabel, yLabel):
		self.plot.setLabels(xLabel, yLabel)


class HistogramPlotDlg(PlotDlg):
	def __init__(self, *args, **kwargs):
		PlotDlg.__init__(self, *args, **kwargs)

	def createPlot(self, *args, **kwargs):
		return HistogramPlotWdg(*args, **kwargs)


# import the NavigationToolbar Qt4Agg widget
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT

class NavigationToolbar(NavigationToolbar2QT):

	def __init__(self, *args, **kwargs):
		NavigationToolbar2QT.__init__(self, *args, **kwargs)

		self.init_buttons()
		self.panAction.setCheckable(True)
		self.zoomAction.setCheckable(True)

		# remove the subplots action
		self.removeAction( self.subplotsAction )

	def configure_subplots(self, *args):
		pass	# do nothing

	class Cursor:
		# cursors defined in backend_bases (from matplotlib source code)
		HAND, POINTER, SELECT_REGION, MOVE = range(4)

		@classmethod
		def toQCursor(self, cursor):
			if cursor == self.MOVE:
				n = Qt.SizeAllCursor
			elif cursor == self.HAND:
				n = Qt.PointingHandCursor
			elif cursor == self.SELECT_REGION:
				n = Qt.CrossCursor
			else:#if cursor == self.POINTER:
				n = Qt.ArrowCursor
			return QCursor( n )

	def set_cursor(self, cursor):
		if cursor != self._lastCursor:
			self.unset_cursor()
			QApplication.setOverrideCursor( NavigationToolbar.Cursor.toQCursor(cursor) )
			self._lastCursor = cursor

	def unset_cursor(self):
		if self._lastCursor:
			QApplication.restoreOverrideCursor()
			self._lastCursor = None

	def init_buttons(self):
		self.homeAction = self.panAction = self.zoomAction = self.subplotsAction = None

		for a in self.actions():
			if a.text() == 'Home':
				self.homeAction = a
			elif a.text() == 'Pan':
				self.panAction = a
			elif a.text() == 'Zoom':
				self.zoomAction = a
			elif a.text() == 'Subplots':
				self.subplotsAction = a

	def resetActionsState(self, skip=None):
		# reset the buttons state
		for a in self.actions():
			if skip and a == skip:
				continue
			a.setChecked( False )

	def pan( self, *args ):
		self.resetActionsState( self.panAction )
		NavigationToolbar2QT.pan( self, *args )

	def zoom( self, *args ):
		self.resetActionsState( self.zoomAction )
		NavigationToolbar2QT.zoom( self, *args )


class ClippedLine2D(Line2D):
	"""
	Clip the xlimits to the axes view limits
	"""

	def __init__(self, *args, **kwargs):
		Line2D.__init__(self, *args, **kwargs)

	def draw(self, renderer):
		x, y = self.get_data()

		if len(x) == 2 or len(y) == 2:
			xlim = self.axes.get_xlim()
			ylim = self.axes.get_ylim()

			x0, y0 = x[0], y[0]
			x1, y1 = x[1], y[1]

			if x0 == x1:	# vertical
				x, y = (x0, x0), ylim
			elif y0 == y1:	# horizontal
				x, y = xlim, (y0, y0)
			else:
				# coeff != 0
				coeff = float(y1 - y0) / (x1 - x0)

				minx = (ylim[0] - y0) / coeff + x0
				maxx = (ylim[1] - y0) / coeff + x0
				miny = coeff * (xlim[0] - x0) + y0
				maxy = coeff * (xlim[1] - x0) + y0

				if coeff > 0:
					x = max(minx, xlim[0]), min(maxx, xlim[1])
					y = max(miny, ylim[0]), min(maxy, ylim[1])
				else:
					x = max(maxx, xlim[0]), min(minx, xlim[1])
					y = min(miny, ylim[1]), max(maxy, ylim[0])

			self.set_data(x, y)

		Line2D.draw(self, renderer)
        
if __name__ == "__main__":
	# for command-line arguments
	import sys

	# Create the GUI application
	app = QApplication(sys.argv)

	# show a histogram plot
	HistogramPlotWdg( [[1,2,1,1,4,3,4,5]], ["x", "y"] ).show()

	# show a scatter plot
	ScatterPlotWdg( data=([1,2,3,4,5],[10,9,7,4,0]), labels=("x", "y"), title="ScatterPlot" ).show()

	# start the Qt main loop execution, exiting from this script
	# with the same return code of Qt application
	sys.exit(app.exec_())

