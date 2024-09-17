$shellapp = New-Object -ComObject Shell.Application
$shellapp.Namespace("shell:Personal").Self.Path
$shellapp.Namespace("shell:My Music").Self.Path
$shellapp.Namespace("shell:My Pictures").Self.Path
$shellapp.Namespace("shell:My Video").Self.Path
$shellapp.Namespace("shell:Downloads").Self.Path
