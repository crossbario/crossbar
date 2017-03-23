# Node Templates

Crossbar.io is able to generate a node from node templates. This directory
contains these node templates.

## Licensing

The code for application templates within this folder (and folders beneath) is licensed under the [BSD 2-clause open-source license](http://opensource.org/licenses/BSD-2-Clause).

The same licenses applie to the code *generated* from the templates here. E.g., when you do

	crossbar init --template default --appdir $HOME/mynode

Crossbar.io will generate a new node in the `$HOME/mynode` directory from the application template in [default](hello/default). All files generated in `$HOME/mynode` are licensed under above licenses.
