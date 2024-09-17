$arr = "MyDocuments","MyMusic","MyPictures","MyVideos"
foreach($v in $arr) {
    [Environment]::GetFolderPath([Environment+SpecialFolder]::$v)
}
