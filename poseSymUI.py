
from baseMelUI import *
from filesystem import Path

import maya.cmds as cmd
import poseSym
import os

LabelledIconButton = labelledUIClassFactory( MelIconButton )


class PoseSymLayout(MelVSingleStretchLayout):

	ICONS = ICON_SWAP, ICON_MIRROR, ICON_MATCH = 'poseSym_swap.xpm', 'poseSym_mirror.xpm', 'poseSym_match.xpm'

	def __init__( self, parent ):
		self.UI_swap = swap = LabelledIconButton( self, llabel='swap pose', llabelWidth=65, llabelAlign='right', c=self.on_swap )
		swap.setImage( self.ICON_SWAP )

		self.UI_mirror = mirror = LabelledIconButton( self, llabel='mirror pose', llabelWidth=65, llabelAlign='right', c=self.on_mirror )
		mirror.setImage( self.ICON_MATCH )

		#self.UI_match = match = LabelledIconButton( self, llabel='match pose', llabelWidth=65, llabelAlign='right', c=self.on_match )
		#match.setImage( self.ICON_MATCH )

		spacer = MelSpacer( self )

		hLayout = MelHLayout( self )
		MelLabel( hLayout, l='mirror: ' )
		self.UI_mirror_t = MelCheckBox( hLayout, l='translate', v=1 )
		self.UI_mirror_r = MelCheckBox( hLayout, l='rotate', v=1 )
		self.UI_mirror_other = MelCheckBox( hLayout, l='other', v=1 )
		hLayout.layout()

		self.setStretchWidget( spacer )
		self.layout()

	### EVENT HANDLERS ###
	def on_swap( self, *a ):
		for pair, obj in poseSym.iterPairAndObj( cmd.ls( sl=True ) ):
			pair.swap( t=self.UI_mirror_t.getValue(), r=self.UI_mirror_r.getValue(), other=self.UI_mirror_other.getValue() )
	def on_mirror( self, *a ):
		for pair, obj in poseSym.iterPairAndObj( cmd.ls( sl=True ) ):
			pair.mirror( obj==pair.controlA, t=self.UI_mirror_t.getValue(), r=self.UI_mirror_r.getValue(), other=self.UI_mirror_other.getValue() )
	def on_match( self, *a ):
		for pair, obj in poseSym.iterPairAndObj( cmd.ls( sl=True ) ):
			pair.match( obj==pair.controlA, t=self.UI_mirror_t.getValue(), r=self.UI_mirror_r.getValue(), other=self.UI_mirror_other.getValue() )


class PoseSymWindow(BaseMelWindow):
	WINDOW_NAME = 'PoseSymTool'
	WINDOW_TITLE = 'Pose Symmetry Tool'

	DEFAULT_SIZE = 280, 200
	DEFAULT_MENU = 'Setup'

	HELP_MENU = WINDOW_NAME, 'hamish@valvesoftware.com', 'https://intranet.valvesoftware.com/wiki/index.php/Pose_Mirror_Tool'

	FORCE_DEFAULT_SIZE = True

	def __init__( self ):
		self.editor = PoseSymLayout( self )
		self.setupMenu()
		self.show()
	def setupMenu( self ):
		menu = self.getMenu( 'Setup' )

		menu.clear()

		MelMenuItem( menu, l='Create Paired Mirror', ann='Will put the two selected objects into a "paired" relationship - they will know how to mirror/exchange poses with one another', c=self.on_setupPair )
		MelMenuItem( menu, l='Create Single Mirror', ann='Will setup the selected control with a mirror node so it knows how to mirror poses on itself', c=self.on_setupSingle )
		MelMenuItemDiv( menu )
		MelMenuItem( menu, l='Auto Setup Skeleton Builder', ann='Tries to determine mirroring relationships from skeleton builder', c=self.on_setupSingle )

	### EVENT HANDLERS ###
	def on_setupPair( self, *a ):
		sel = cmd.ls( sl=True, type='transform' )
		if len( sel ) == 1:
			pair = poseSym.ControlPair.Create( sel[0] )
			cmd.select( pair.node )
		elif len( sel ) >= 2:
			pair = poseSym.ControlPair.Create( sel[0], sel[1] )
			cmd.select( pair.node )
	def on_setupSingle( self, *a ):
		sel = cmd.ls( sl=True, type='transform' )
		if len( sel ) == 1:
			pair = poseSym.ControlPair.Create( sel[0] )
			cmd.select( pair.node )
	def on_setupSkeletonBuilder( self, *a ):
		import rigPrimitives
		rigPrimitives.setupMirroring()


#end
