
from maya import cmds as cmd


def d_showWaitCursor(f):
	'''
	turns the wait cursor on while the decorated method is executing, and off again once finished
	'''
	def func( *args, **kwargs ):
		cmd.waitCursor( state=True )
		try:
			return f( *args, **kwargs )
		finally:
			cmd.waitCursor( state=False )

	func.__name__ = f.__name__
	func.__doc__ = f.__doc__

	return func


def d_disableViews(f):
	'''
	disables all viewports before, and re-enables them after
	'''
	def func( *args, **kwargs ):
		modelPanels = cmd.getPanel( vis=True )
		emptySelConn = cmd.selectionConnection()

		for panel in modelPanels:
			if cmd.getPanel( to=panel ) == 'modelPanel':
				cmd.isolateSelect( panel, state=True )
				cmd.modelEditor( panel, e=True, mlc=emptySelConn )

		try:
			return f( *args, **kwargs )
		finally:
			for panel in modelPanels:
				if cmd.getPanel( to=panel ) == 'modelPanel':
					cmd.isolateSelect( panel, state=False )

			cmd.deleteUI( emptySelConn )

	func.__name__ = f.__name__
	func.__doc__ = f.__doc__

	return func


def d_autoKey(f):
	'''
	forces autoKey on
	'''
	def func( *args, **kwargs ):
		initialState = cmd.autoKeyframe( q=True, state=True )
		cmd.autoKeyframe( state=True )
		try:
			return f( *args, **kwargs )
		finally:
			cmd.autoKeyframe( state=initialState )

	func.__name__ = f.__name__
	func.__doc__ = f.__doc__

	return func


def d_noAutoKey(f):
	'''
	forces autoKey off
	'''
	def func( *args, **kwargs ):
		initialState = cmd.autoKeyframe( q=True, state=True )
		cmd.autoKeyframe( state=False )
		try:
			return f( *args, **kwargs )
		finally:
			cmd.autoKeyframe( state=initialState )

	func.__name__ = f.__name__
	func.__doc__ = f.__doc__

	return func


def d_restoreTime(f):
	'''
	restores the initial time once the wrapped function exits
	'''
	def func( *args, **kwargs ):
		initialTime = cmd.currentTime( q=True )
		try:
			return f( *args, **kwargs )
		finally:
			cmd.currentTime( initialTime, e=True )

	func.__name__ = f.__name__
	func.__doc__ = f.__doc__

	return func


def d_noUndo(f):
	'''
	forces undo off
	'''
	def func( *args, **kwargs ):
		initialState = cmd.undoInfo( q=True, state=True )
		cmd.undoInfo( stateWithoutFlush=False )
		try:
			return f( *args, **kwargs )
		finally:
			cmd.undoInfo( stateWithoutFlush=initialState )

	func.__name__ = f.__name__
	func.__doc__ = f.__doc__

	return func


def d_unifyUndo(f):
	'''
	wraps the function into a definite undo "chunk" - why this needs to be done for python is beyond me...
	'''
	def func( *args, **kwargs ):
		cmd.undoInfo( openChunk=True )
		try:
			return f( *args, **kwargs )
		finally:
			cmd.undoInfo( closeChunk=True )

	func.__name__ = f.__name__
	func.__doc__ = f.__doc__

	return func


def d_progress( **dec_kwargs ):
	'''
	deals with progress window...  any kwargs given to the decorator on init are passed to the progressWindow init method
	'''
	def ffunc(f):
		def func( *args, **kwargs ):
			try:
				cmd.progressWindow( **dec_kwargs )
			except: print 'error init-ing the progressWindow'

			try:
				return f( *args, **kwargs )
			finally:
				cmd.progressWindow( ep=True )

		func.__name__ = f.__name__
		func.__doc__ = f.__doc__

		return func

	return ffunc


_ANIM_LAYER_ATTRS = [ 'mute',
                      'solo',
                      'lock',
                      'override',
                      #'passthrough',
                      'weight',
                      #'parentMute',
                      #'childsoloed',
                      #'siblingSolo',
                      #'outMute',
                      'preferred',
                      'selected',
                      'collapse',
                      'backgroundWeight' ]

if mayaVer >= 2011:
	_ANIM_LAYER_ATTRS += [ 'rotationAccumulationMode',
	                       'scaleAccumulationMode' ]
else:
	_ANIM_LAYER_ATTRS += [ 'rotationInterpolateMode',
	                       'scaleInterpolateMode' ]


def d_restoreAnimLayers( f ):
	'''
	restores animation layer state -
	'''

	#if this excepts, just return the function as is - anim layers aren't supported by this version
	try:
		cmd.ls( typ='animLayer' )
	except RuntimeError: return f

	def func( *a, **kw ):
		#store pre-function values
		preDict = {}
		selectedLayers = []
		for l in cmd.ls( typ='animLayer' ):
			preDict[ l ] = valueDict = {}
			if cmd.animLayer( l, q=True, selected=True ):
				selectedLayers.append( l )

			for attr in _ANIM_LAYER_ATTRS:
				valueDict[ attr ] = cmd.getAttr( '%s.%s' % (l, attr) )

		#run the function
		try:
			f( *a, **kw )
		finally:
			#restore selection and all layer attributes
			for l, valueDict in preDict.iteritems():
				for attr, value in valueDict.iteritems():
					try: cmd.setAttr( '%s.%s' % (l, attr), value )
					except RuntimeError: pass

			for l in cmd.ls( typ='animLayer' ):
				cmd.animLayer( l, e=True, selected=False )

			for l in selectedLayers:
				cmd.animLayer( l, e=True, selected=True )

			cmd.animLayer( forceUIRefresh=True )

	func.__name__ = f.__name__
	func.__doc__ = f.__doc__

	return func


def d_maintainSceneSelection(f):
	def wrapped( *a, **kw ):
		initSel = cmd.ls( sl=True )
		try:
			f( *a, **kw )
		finally:
			if cmd.ls( sl=True ) != initSel:
				initSel = [ o for o in initSel if cmd.objExists( o ) ]
				if initSel:
					cmd.select( initSel )

	wrapped.__name__ = f.__name__
	wrapped.__doc__ = f.__doc__

	return wrapped


#end
