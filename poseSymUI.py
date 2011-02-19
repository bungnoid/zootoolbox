
from baseMelUI import *

import poseSym

LabelledIconButton = labelledUIClassFactory( MelIconButton )


class PoseSymLayout(MelColumnLayout):
	ICONS = ICON_SWAP, ICON_MIRROR, ICON_MATCH = 'poseSym_swap', 'poseSym_mirror.png', 'poseSym_match.png'

	def __init__( self, parent ):
		self.UI_swap = swap = LabelledIconButton( self, llabel='swap pose', llabelWidth=65, llabelAlign='right', c=self.on_swap )
		swap.setImage( self.ICON_SWAP )

		self.UI_mirror = mirror = LabelledIconButton( self, llabel='mirror pose', llabelWidth=65, llabelAlign='right', c=self.on_mirror )
		mirror.setImage( self.ICON_MATCH )

		#self.UI_match = match = LabelledIconButton( self, llabel='match pose', llabelWidth=65, llabelAlign='right', c=self.on_match )
		#match.setImage( self.ICON_MATCH )

	### EVENT HANDLERS ###
	def on_swap( self, *a ):
		for pair in poseSym.getPairsFromSelection():
			pair.swap()
	def on_mirror( self, *a ):
		for pair in poseSym.getPairsFromSelection():
			pair.mirror()
	def on_match( self, *a ):
		for pair in poseSym.getPairsFromSelection():
			pair.match()


class PoseSymWindow(BaseMelWindow):
	WINDOW_NAME = 'PoseSymTool'
	WINDOW_TITLE = 'Pose Symmetry Tool'

	DEFAULT_SIZE = 300, 300
	DEFAULT_MENU = None  #'Help'
	DEFAULT_MENU_IS_HELP = True

	#HELP_MENU = WINDOW_NAME, 'hamish@valvesoftware.com', 'https://intranet.valvesoftware.com/wiki/index.php/Space_Switching'

	FORCE_DEFAULT_SIZE = True

	def __init__( self ):
		PoseSymLayout( self )
		self.show()


#end
