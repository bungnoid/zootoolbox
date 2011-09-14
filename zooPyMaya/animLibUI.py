
from baseMelUI import *
from animLib import *
from presetsUI import addExploreToMenuItems

import presetsUI
import xferAnimUI

__author__ = 'hamish@macaronikazoo.com'


def getSelectedChannelBoxAttrNames():
	attrNames = cmd.channelBox( 'mainChannelBox', q=True, sma=True ) or []
	attrNames += cmd.channelBox( 'mainChannelBox', q=True, ssa=True ) or []
	attrNames += cmd.channelBox( 'mainChannelBox', q=True, sha=True ) or []

	return attrNames


class AnimLibClipLayout(MelForm):
	SLIDER_VISIBLE = { kPOSE: True,
	                   kANIM: False }

	def __new__( cls, parent, library, locale, clipPreset ):
		return MelHLayout.__new__( cls, parent )

	def __init__( self, parent, library, locale, clipPreset ):
		MelForm.__init__( self, parent )

		self.clipPreset = clipPreset
		self.name = self.clipPreset.niceName
		self.isActive = False
		self.preClip = {}
		self.objs = []
		self.mapping = {}
		self.type = self.clipPreset.getType()

		self.optionsLayout = self.getParentOfType( AnimLibLayout )

		#cache the apply method locally - mainly for brevity in subsequent code...
		self.apply = clipPreset.apply

		#read the clip and cache some data...
		self.blended = None

		self.build()
	def build( self ):
		'''
		populates the top level form with ui widgets
		'''
		self.UI_icon = MelIconButton( self, l=self.name(), image=str(self.clipPreset.icon()), w=kICON_W_H[0], h=kICON_W_H[1], c=self.onApply, sourceType='python', ann="click the icon to apply the clip, or use the slider to partially apply it.  if you don't like the icon, right click and choose re-generate icon" )

		typeLbl = ClipPreset.TYPE_LABELS[ self.clipPreset.getType() ]
		self.UI_lbl = MelLabel( self, l='%s clip:  %s' % (typeLbl, self.name()), font='boldLabelFont', ann="this is the clip's name.  right click and choose rename to change the clip's name" )

		#setup the slider
		self.UI_slider = MelFloatSlider( self, v=0, min=0, max=1, ann='use the slider to partially apply a clip, or click the icon to apply it completely' )
		self.UI_slider.setPreChangeCB( self.preDrag )
		self.UI_slider.setChangeCB( self.onDrag )
		self.UI_slider.setPostChangeCB( self.postDrag )
		self.UI_slider.DISABLE_UNDO_ON_DRAG = True
		self.UI_slider.setVisibility( self.SLIDER_VISIBLE[ self.type ] )

		MelPopupMenu( self, pmc=self.buildMenu )

		#do layout
		self( e=True,
		      af=((self.UI_icon, 'left', 0),
		          (self.UI_lbl, 'top', 2),
		          (self.UI_lbl, 'right', 0),
		          (self.UI_slider, 'top', 20),
		          (self.UI_slider, 'right', 0)),
		      ac=((self.UI_lbl, 'left', 10, self.UI_icon),
		          (self.UI_slider, 'left', 0, self.UI_icon)) )
	def unpickle( self ):
		return self.clipPreset.unpickle()
	@property
	def clipObjs( self ):
		return self.unpickle()[ 'objects' ]
	@property
	def clipInstance( self ):
		return self.unpickle()[ 'clip' ]
	def onApply( self, slam=False ):
		opts = self.optionsLayout.getOptions()
		opts[ 'slam' ] = slam

		if opts[ 'attrSelection' ]:
			attributes = cmd.channelBox( 'mainChannelBox', q=True, sma=True ) or cmd.channelBox( 'mainChannelBox', q=True, sha=True ) or None
		else:
			attributes = None

		self.apply( cmd.ls(sl=True), attributes, **opts )
	def buildMenu( self, parent, *args ):
		cmd.setParent( parent, m=True )
		cmd.menu( parent, e=True, dai=True )

		cmd.menuItem( l=self.name(), boldFont=True )
		if self.clipPreset.locale() == LOCAL:
			cmd.menuItem( l='publish to global -->', c=self.onPublish )

		def onIcon(*x):
			generateIcon(self.clipPreset)
			self.refreshIcon()

		cmd.menuItem( l='re-generate icon', c=onIcon )
		cmd.menuItem( d=True )
		cmd.menuItem( l='delete', c=lambda *x: self.delete() )
		cmd.menuItem( l='rename', c=self.onRename )
		cmd.menuItem( d=True )

		cmd.menuItem( l='slam clip into scene', c=self.onSlam )
		cmd.menuItem( l='select items in clip', c=self.onSelect )
		cmd.menuItem( l='map names manually', c=self.onMapping )
		cmd.menuItem( d=True )
		cmd.menuItem( l='edit clip', c=self.onEdit )
		cmd.menuItem( d=True )
		addExploreToMenuItems( self.clipPreset.path() )
	def onPublish( self, *args ):
		movedPreset = self.clipPreset.move()

		self.delete()
		self.sendEvent( 'populateClips' )
	def onSelect( self, arg ):
		objs = self.clipPreset.getClipObjects()
		existingObjs = []
		sceneTransforms = cmd.ls( typ='transform' )
		for o in objs:
			if not cmd.objExists( o ):
				newO = names.matchNames( [o], sceneTransforms, threshold=kDEFAULT_MAPPING_THRESHOLD )[ 0 ]
				if not cmd.objExists( newO ):
					print 'WARNING :: %s NOT FOUND IN SCENE!!!' % o
					continue

				existingObjs.append( newO )
				print 'WARNING :: re-mapping %s to %s' % (o, newO)
			else:
				existingObjs.append( o )

		cmd.select( existingObjs )
	def onSlam( self, arg ):
		self.onApply( True )
	def onMapping( self, *args ):
		mapping = Mapping( cmd.ls(sl=True), self.clipObjs )

		#convert the mapping to the type of mapping expected by the xfer anim editor - ie a single source maps to a list of targets instead of a single target...
		xferAnimMapping = {}
		for src, tgt in mapping.iteritems():
			xferAnimMapping[ src ] = [ tgt ]

		xferAnimUI.XferAnimWindow( mapping=xferAnimMapping, clipPreset=self.clipPreset )
	def onEdit( self, *args ):
		AnimClipChannelEditorWindow( self.clipPreset )
	def onRename( self, *args ):
		BUTTONS = OK, CANCEL = 'Ok', 'Cancel'
		ans = cmd.promptDialog( t='new name', m='enter new name', tx=self.name(), b=BUTTONS, db=OK )
		if ans != OK:
			return

		name = cmd.promptDialog( q=True, tx=True )
		if not name:
			return

		self.clipPreset = self.clipPreset.rename( name )
		self.clear()
		self.populateUI()
	def preDrag( self ):
		self.autoKeyBeginState = cmd.autoKeyframe( q=True, state=True )
		cmd.autoKeyframe( e=True, state=False )

		opts = self.optionsLayout.getOptions()
		if opts[ 'attrSelection' ]:
			attributes = cmd.channelBox( 'mainChannelBox', q=True, sma=True ) or cmd.channelBox( 'mainChannelBox', q=True, sha=True ) or None
		else:
			attributes = None

		self.objs = objs = cmd.ls( sl=True )

		tgts = names.matchNames( self.clipObjs, objs, threshold=kDEFAULT_MAPPING_THRESHOLD )
		self.mapping = mapping = Mapping( tgts, self.clipObjs )

		self.preClip = self.clipInstance.__class__( objs, *self.clipInstance.generatePreArgs() )
		self.blended = self.clipInstance.blender( self.preClip, self.clipInstance, mapping, attributes )
	def onDrag( self, value ):
		value = float( value )
		self.blended( value )
	def postDrag( self, value ):
		cmd.autoKeyframe( e=True, state=self.autoKeyBeginState )

		value = float( value )
		self.blended( value )
		self.reset()
	def refreshIcon( self ):
		self.UI_icon.refresh()
	def delete( self ):
		self.clipPreset.delete()

		MelForm.delete( self )
	def reset( self ):
		self.UI_slider.reset( False )


class AnimClipChannelEditorLayout(MelVSingleStretchLayout):
	def __init__( self, parent, clipPreset ):
		MelVSingleStretchLayout.__init__( self, parent )

		self.clipPreset = clipPreset
		self.presetDict = presetDict = clipPreset.unpickle()
		self.clipDict = clipDict = presetDict[ 'clip' ]
		self._dirty = False

		#build the UI
		hLayout = MelHLayout( self )
		vLayout = MelVSingleStretchLayout( hLayout )
		self.UI_objList = UI_objList = MelObjectScrollList( vLayout )
		UI_removeObjs = MelButton( vLayout, l='Remove Selected Objects' )
		vLayout.setStretchWidget( UI_objList )
		vLayout.layout()

		vLayout = MelVSingleStretchLayout( hLayout )
		self.UI_attrList = UI_attrList = MelObjectScrollList( vLayout )
		UI_removeAttrs = MelButton( vLayout, l='Remove Selected Attributes' )
		vLayout.setStretchWidget( UI_attrList )
		vLayout.layout()

		UI_objList.allowMultiSelect( True )
		UI_attrList.allowMultiSelect( True )


		hLayout.expand = True
		hLayout.layout()

		self.setStretchWidget( hLayout )

		#populate the object list
		for obj in clipDict:
			UI_objList.append( obj )


		#build callbacks for the lists
		def objSelected():
			objs = UI_objList.getSelectedItems()
			if not objs:
				return

			UI_attrList.clear()
			attrsAlreadyAdded = set()
			for obj in objs:
				attrDict = clipDict[ obj ]
				for attrName, attrValue in attrDict.iteritems():
					if attrName in attrsAlreadyAdded:
						continue

					self.UI_attrList.append( attrName )
					attrsAlreadyAdded.add( attrName )

				if attrDict:
					self.UI_attrList.selectByIdx( 0, True )

		UI_objList.setChangeCB( objSelected )
		def removeObjs( *a ):
			objs = UI_objList.getSelectedItems()
			if not objs:
				return

			performUpdate = False
			for obj in objs:
				if obj in clipDict:
					self._dirty = True
					performUpdate = True
					clipDict.pop( obj )

			if performUpdate:
				UI_objList.clear()
				UI_attrList.clear()
				for obj in clipDict:
					UI_objList.append( obj )

				if clipDict:
					UI_objList.selectByIdx( 0, True )

		UI_removeObjs.setChangeCB( removeObjs )
		def removeAttrs( *a ):
			objs = UI_objList.getSelectedItems()
			if not objs:
				return

			attrs = UI_attrList.getSelectedItems()
			if not attrs:
				return

			performUpdate = False
			for obj in objs:
				subDict = clipDict[ obj ]
				for attr in attrs:
					self._dirty = True
					performUpdate = True
					if attr in subDict:
						subDict.pop( attr )

			if performUpdate:
				objSelected()

		UI_removeAttrs.setChangeCB( removeAttrs )


		#set the initial state
		if len( self.UI_objList ):
			UI_objList.selectByIdx( 0, True )


		#build the save/cancel UI...
		hLayout = MelHLayout( self )
		MelButton( hLayout, l='Save', c=self.on_save )
		MelButton( hLayout, l='Cancel', c=lambda *a: self.sendEvent( 'delete' ) )
		hLayout.layout()

		self.setDeletionCB( self.on_cancel )
		self.layout()
	def askToSave( self ):
		#check to see if changes were made, and if so, ask if the user wants to save them...
		if self._dirty:
			BUTTONS = YES, NO, CANCEL = 'Yes', 'No', 'Cancel'
			ret = cmd.confirmDialog( t='Overwrite Clip?',
			                         m='Are you sure you want to overwrite the %s clip called %s?' % (ClipPreset.TYPE_LABELS[ self.clipPreset.getType() ],
			                                                                                          self.clipPreset.name().split( '.' )[0]),
			                         b=BUTTONS, db=CANCEL )
			if ret == CANCEL:
				return False
			elif ret == YES:
				self.clipPreset.pickle( self.presetDict )
				self._dirty = False

		return True

	### EVENT HANDLERS ###
	def on_cancel( self, *a ):
		self.askToSave()
	def on_save( self, *a ):
		if self.askToSave():
			self.sendEvent( 'delete' )


class AnimClipChannelEditorWindow(BaseMelWindow):
	WINDOW_NAME = 'animClipEditor'
	WINDOW_TITLE = 'Anim Clip Editor'

	DEFAULT_MENU = None
	DEFAULT_SIZE = 400, 250

	FORCE_DEFAULT_SIZE = False

	def __init__( self, clipPreset ):
		BaseMelWindow.__init__( self )
		AnimClipChannelEditorLayout( self, clipPreset )
		self.show()


class AnimLibLocaleLayout(MelVSingleStretchLayout):
	def __init__( self, parent, clipManager, locale ):
		MelVSingleStretchLayout.__init__( self, parent )

		self._locale = locale
		self._clipManager = clipManager
		self._filterStr = None
		self._libraries = None

		if locale == GLOBAL:
			hLayout = MelHLayout( self )
			MelLabel( hLayout, l='global clips' )
			MelButton( hLayout, l='sync global clips', c=self.on_sync )
			hLayout.layout()
		else:
			MelLabel( self, l='local clips' )

		scroll = MelScrollLayout( self )
		self.UI_clips = MelColumnLayout( scroll )
		self.setStretchWidget( scroll )
		self.layout()

		MelPopupMenu( self, pmc=self.buildMenu )
	def setLibraries( self, libraries ):
		self._libraries = libraries
		self.populate()
	def getClips( self ):
		clips = {}
		for library in self._libraries:
			clips[ library ] = self._clipManager.getLibraryClips( library )[ self._locale ]

		return clips
	def populate( self ):
		self.UI_clips.clear()

		filterStr = self._filterStr
		clips = self.getClips()

		for library, clips in clips.iteritems():
			for clip in clips:
				clipName = clip.niceName()
				addClip = False
				if filterStr:
					if filterStr in clipName:
						addClip = True
				else:
					addClip = True

				if addClip:
					AnimLibClipLayout( self.UI_clips, library, self._locale, clip )
	def getFilter( self ):
		return self._filterStr
	def setFilter( self, filterStr ):
		self._filterStr = filterStr
		self.populate()
	def buildMenu( self, parent, *args ):
		cmd.setParent( parent, m=True )
		cmd.menu( parent, e=True, dai=True )

		cmd.menuItem( l='new pose clip', c=lambda *x: self.sendEvent( 'newClip', kPOSE ) )
		cmd.menuItem( l='new anim clip', c=lambda *x: self.sendEvent( 'newClip', kANIM ) )
	def on_sync( self, *a ):
		#p4run( 'sync', *self._clipManager.getPresetDirs( GLOBAL ) )

		self.populate()
		self.sendEvent( 'populateLibraries' )


class AnimLibLayout(MelHSingleStretchLayout):
	def __init__( self, parent ):
		MelHSingleStretchLayout.__init__( self, parent )

		AnimClipChannelEditorWindow.Close()

		self._clipManager = clipManager = ClipManager()

		vLayout = MelVSingleStretchLayout( self )
		MelLabel( vLayout, l='clip libraries' )

		hLayout = MelHSingleStretchLayout( vLayout )
		MelLabel( hLayout, l='filter' )
		self.UI_filter = MelTextField( hLayout, cc=self.on_filter )
		MelButton( hLayout, l='clear', c=lambda *a: self.UI_filter.clear() )
		hLayout.setStretchWidget( self.UI_filter )
		hLayout.layout()

		self.UI_libraries = MelObjectScrollList( vLayout, ams=True )
		self.UI_libraries.setChangeCB( self.on_selectLibrary )
		self.UI_newLibrary = MelButton( vLayout, l='new library', w=150, c=self.on_newLibrary )
		vLayout.setStretchWidget( self.UI_libraries )
		vLayout.layout()


		#this is the layout for everything on the right side of the library list
		paneLayout = MelVSingleStretchLayout( self )


		#add clip filter UI
		hLayout = MelHSingleStretchLayout( paneLayout )
		MelSpacer( hLayout )
		MelLabel( hLayout, l='filter clips' )
		self.UI_filterClips = MelTextField( hLayout, cc=self.on_filterClips )
		MelButton( hLayout, l='clear', c=lambda *a: self.UI_filterClips.clear() )
		hLayout.setStretchWidget( self.UI_filterClips )
		hLayout.layout()


		#add the libraries
		self.UI_panes = MelHLayout( paneLayout )
		self.UI_panes.expand = True

		self.UI_local = AnimLibLocaleLayout( self.UI_panes, clipManager, LOCAL )
		self.UI_global = AnimLibLocaleLayout( self.UI_panes, clipManager, GLOBAL )
		self.UI_panes.layout()


		#add the load options
		hLayout = MelHRowLayout( paneLayout )
		self.UI_opt_currentTime = MelCheckBox( hLayout, l='load clip at current time', v=True )
		self.UI_opt_additive = MelCheckBox( hLayout, l='load additively' )
		#self.UI_opt_currentTime = MelCheckBox( hLayout, l='load additively in world', en=False )
		self.UI_opt_attrSelection = MelCheckBox( hLayout, l='use attribute selection', v=BaseClip.kOPT_DEFAULTS[ BaseClip.kOPT_ATTRSELECTION ] )
		hLayout.layout()


		#add the "new" buttons
		hLayout = MelHLayout( paneLayout )
		MelButton( hLayout, l='new pose clip', c=self.on_newPose )
		MelButton( hLayout, l='new anim clip', c=self.on_newAnim )
		hLayout.layout()

		paneLayout.setStretchWidget( self.UI_panes )
		paneLayout.layout()

		self.setStretchWidget( paneLayout )
		self.setExpand( True )
		self.layout()

		self.populateLibraries()
		self.setDeletionCB( self.on_close )
	def populateLibraries( self ):
		UI_libraries = self.UI_libraries
		UI_libraries.clear()

		libraryNames = self._clipManager.getLibraryNames()
		for library in libraryNames:
			UI_libraries.append( library )

		if libraryNames:
			self.UI_libraries.selectByIdx( 0, True )

		self.UI_libraries.setFocus()
	def populateClips( self ):
		self.UI_local.populate()
		self.UI_global.populate()
	def getOptions( self ):
		opts = {}
		opts[ BaseClip.kOPT_OFFSET ] = cmd.currentTime( q=True ) if self.UI_opt_currentTime.getValue() else 0
		opts[ BaseClip.kOPT_ADDITIVE ] = self.UI_opt_additive.getValue()
		opts[ BaseClip.kOPT_ATTRSELECTION ] = self.UI_opt_attrSelection.getValue()

		return opts
	def getLocalVisibility( self ):
		return self.UI_local.getVisibility()
	def setLocalVisibility( self, showState ):
		#if the global is currently invisible, turn it on - no point having neither local or global invisible...
		if not self.UI_global.getVisibility():
			self.setGlobalVisibility( True )

		self.UI_local.setVisibility( showState )
		self.UI_panes.setWeight( self.UI_local, int( showState ) )
		self.UI_panes.layout()
	def getGlobalVisibility( self ):
		return self.UI_global.getVisibility()
	def setGlobalVisibility( self, showState ):
		#if the local is currently invisible, turn it on - no point having neither local or global invisible...
		if not self.UI_local.getVisibility():
			self.setLocalVisibility( True )

		self.UI_global.setVisibility( showState )
		self.UI_panes.setWeight( self.UI_global, int( showState ) )
		self.UI_panes.layout()
	def newClip( self, clipType ):
		theLibrary = self.UI_libraries.getSelectedItems()
		if not theLibrary:
			return

		theLibrary = theLibrary[0]

		BUTTONS = OK, CANCEL = 'OK', 'Cancel'
		typeLabel = ClipPreset.TYPE_LABELS[ clipType ]
		ans = cmd.promptDialog( t='enter %s name' % typeLabel, m='enter the %s name:' % typeLabel, b=BUTTONS, db=OK )
		if ans == CANCEL:
			return

		kwargs = {}

		opts = self.getOptions()
		if opts.get( 'attrSelection', False ):
			kwargs[ 'attrs' ] = getSelectedChannelBoxAttrNames() or None

		if clipType == kANIM:
			kwargs = { 'startFrame': cmd.playbackOptions( q=True, min=True ),
			           'endFrame': cmd.playbackOptions( q=True, max=True ) }

		objs = cmd.ls( sl=True )
		name = cmd.promptDialog( q=True, tx=True )
		newClip = ClipPreset( LOCAL, theLibrary, name, clipType )
		newClip.write( objs, **kwargs )

		#add the clip to the UI
		self.UI_local.populate()

	### EVENT HANDLERS ###
	def on_close( self, *a ):
		AnimClipChannelEditorWindow.Close()
	def on_selectLibrary( self, *a ):
		sel = self.UI_libraries.getSelectedItems()
		if sel:
			self.UI_local.setLibraries( sel )
			self.UI_global.setLibraries( sel )
	def on_newLibrary( self, *a ):
		BUTTONS = OK, CANCEL = 'OK', 'Cancel'
		ans = cmd.promptDialog( t='enter library name', m='enter the library name:', b=BUTTONS, db=OK )
		if ans == CANCEL:
			return

		name = cmd.promptDialog( q=True, tx=True )
		self._clipManager.createLibrary( name )

		self.populateLibraries()

		self.UI_libraries.clearSelection()
		self.UI_libraries.selectByValue( name )
		self.UI_local.setLibraries( name )
		self.UI_global.setLibraries( name )
	def on_newPose( self, *args ):
		self.newClip( kPOSE )
	def on_newAnim( self, *args ):
		self.newClip( kANIM )
	def on_filter( self, *a ):
		self.UI_libraries.setFilter( self.UI_filter.getValue() )

		#if there are no selected items, check to see if there are any items and if so select the first one
		if not self.UI_libraries.getSelectedIdxs():
			if self.UI_libraries.getItems():
				self.UI_libraries.selectByIdx( 0, True )
	def on_filterClips( self, *a ):
		filterStr = self.UI_filterClips.getValue()

		self.UI_local.setFilter( filterStr )
		self.UI_global.setFilter( filterStr )


class AnimLibWindow(BaseMelWindow):
	WINDOW_NAME = 'animLibraryWindow'
	WINDOW_TITLE = 'Animation Library'

	DEFAULT_SIZE = 750, 400
	FORCE_DEFAULT_SIZE = True

	DEFAULT_MENU = 'Show'
	HELP_MENU = TOOL_NAME, __author__, None

	def __init__( self ):
		BaseMelWindow.__init__( self )

		showMenu = self.getMenu( self.DEFAULT_MENU )
		showMenu( e=True, pmc=self.buildShowMenu )

		self.UI_editor = AnimLibLayout( self )
		self.show()
	def buildShowMenu( self, *w ):
		showMenu = self.getMenu( self.DEFAULT_MENU )
		showMenu.clear()

		MelMenuItem( showMenu, l='Show Local Clips', cb=self.UI_editor.getLocalVisibility(), c=self.on_showLocal )
		MelMenuItem( showMenu, l='Show Global Clips', cb=self.UI_editor.getGlobalVisibility(), c=self.on_showGlobal )

	def on_showLocal( self, *a ):
		state = int( a[0] )
		self.UI_editor.setLocalVisibility( state )
	def on_showGlobal( self, *a ):
		state = int( a[0] )
		self.UI_editor.setGlobalVisibility( state )

AnimLibUI = AnimLibWindow


def load():
	#first make sure there is a default library...
	tmp = ClipManager().createLibrary( 'default' )
	AnimLibUI()


#end