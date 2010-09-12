
from baseMelUI import *
from animLib import *

import presetsUI
import xferAnimUI

__author__ = 'mel@macaronikazoo.com'


def getSelectedChannelBoxAttrNames():
	attrNames = cmd.channelBox( 'mainChannelBox', q=True, sma=True ) or []
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
		self.clipContents = None

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
		self.UI_icon = MelIconButton( self, l=self.name(), image=str(self.clipPreset.icon.resolve()), w=kICON_W_H[0], h=kICON_W_H[1], c=self.onApply, sourceType='python', ann="click the icon to apply the clip, or use the slider to partially apply it.  if you don't like the icon, right click and choose re-generate icon" )

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
		if self.clipContents is None:
			self.clipContents = self.clipPreset.unpickle()

		return self.clipContents
	@property
	def clipObjs( self ):
		return self.unpickle()[ 'objects' ]
	@property
	def clipInstance( self ):
		return self.unpickle()[ 'clip' ]
	def onApply( self, slam=False ):
		opts = self.optionsLayout.getOptions()
		opts[ 'slam' ] = slam

		self.mapping = Mapping( cmd.ls(sl=True), self.clipObjs )
		self.apply( self.mapping, **opts )
	def buildMenu( self, parent, *args ):
		cmd.setParent( parent, m=True )
		cmd.menu( parent, e=True, dai=True )

		cmd.menuItem( l=self.name(), boldFont=True )
		if self.clipPreset.locale == LOCAL:
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
		api.addExploreToMenuItems(self.clipPreset)
		if self.clipPreset.locale == GLOBAL:
			cmd.menuItem( d=True )
			api.addPerforceMenuItems( self.clipPreset, others=[self.clipPreset.icon], previous=False )
	def onPublish( self, *args ):
		movedPreset = self.clipPreset.move()

		#add to perforce
		p4 = P4File( movedPreset )
		p4.DEFAULT_CHANGE = 'animLib Auto Checkout'
		p4.add( movedPreset, type=P4File.BINARY )
		p4.add( movedPreset.icon, type=P4File.BINARY )

		#ask the user whether they want to submit the clip - delayed submission is rarely useful/desired
		ans = cmd.confirmDialog( t='submit clip now?', m='do you want to submit the clip now', b=api.ui_QUESTION, db=api.YES )
		if ans == api.YES:
			p4.submit()

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

		#gah...  convert the mapping to the type of mapping expected by the xfer anim editor - ie a single source maps to a list of targets instead of a single target...  need to turn the mapping into a class of some description methinks
		xferAnimMapping = {}
		for src, tgt in mapping.iteritems():
			xferAnimMapping[ src ] = [ tgt ]

		xferAnimUI.XferAnimEditor( mapping=xferAnimMapping, clipPreset=self.clipPreset )
	def onRename( self, *args ):
		ans, name = api.doPrompt(t='new name', m='enter new name', tx=self.name())
		if ans != api.OK:
			return

		self.clipPreset = self.clipPreset.rename( name )
		self.clear()
		self.populateUI()
	def preDrag( self ):
		self.autoKeyBeginState = cmd.autoKeyframe( q=True, state=True )
		cmd.autoKeyframe( e=True, state=False )

		self.objs = objs = cmd.ls( sl=True )
		self.mapping = Mapping( objs, self.clipObjs )
		self.preClip = self.clipInstance.__class__( objs, *self.clipInstance.generatePreArgs() )
		self.blended = self.clipInstance.blender( self.preClip, self.clipInstance, self.mapping )
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

		#if the clip is a global clip, ask the user if they want to submit the delete
		if self.clipPreset.locale == GLOBAL:
			ans = cmd.confirmDialog(t='submit the delete?', m='do you want to submit the delete?', b=api.ui_QUESTION, db=api.YES)
			if ans == api.YES:
				p4 = P4File(self.clipPreset)
				p4.DEFAULT_CHANGE = 'auto deleting file from %s' % TOOL_NAME
				p4.setChange( p4.DEFAULT_CHANGE )
				p4.setChange( p4.DEFAULT_CHANGE, self.clipPreset.icon )
				p4.submit()

		MelForm.delete( self )
	def reset( self ):
		self.UI_slider.reset( False )


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
		p4run( 'sync', *self._clipManager.getPresetDirs( GLOBAL ) )

		self.populate()
		self.sendEvent( 'populateLibraries' )


class AnimLibLayout(MelHSingleStretchLayout):
	def __init__( self, parent ):
		MelHSingleStretchLayout.__init__( self, parent )

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

		kwargs = { 'attrs': getSelectedChannelBoxAttrNames() or None }
		if clipType == kANIM:
			kwargs = { 'startFrame': cmd.playbackOptions( q=True, min=True ),
			           'endFrame': cmd.playbackOptions( q=True, max=True ) }

		objs = cmd.ls( sl=True )
		name = cmd.promptDialog( q=True, tx=True )
		newClip = ClipPreset( LOCAL, theLibrary, name, clipType )
		newClip.write( objs, **kwargs )

		#add the clip to the UI
		self.UI_local.populate()

		print 'wrote new %s clip!' % typeLabel, newClip

	### EVENT HANDLERS ###
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