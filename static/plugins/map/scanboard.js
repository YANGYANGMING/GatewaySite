$(function(){

	
	//高德地图
    var myMap = new AMap.Map('myMap',{
        resizeEnable: true,
        zoom: 20,
        // mapStyle: 'amap://styles/darkblue',
        center: [120.7749269800,31.2933466000],
    });
    
    var point = [
    	// [120.7749269800,31.2933466000],
    	// [120.7744227200,31.2931128100],
    	// [120.7760309400,31.2924380200]
	];
    // var maker;
    for (var i = 0; i < point.length; i += 1) {
        var marker = new AMap.Marker({
            position: point[i],
            map: myMap,
            icon:'/static/plugins/map/s_ico4.png',
        });
        marker.content='<p>ZC1712120023</p>'+
				'<p>起点：配件A厂</p>'+
				'<p>终点：美的冰箱公司</p>'+
				'<p>满载率：95%</p>'+
				'<p>已使用时间：2小时15分</p>';
        marker.on('click', markerClick);
        //map.setFitView(); 
    }
    var infoWindow = new AMap.InfoWindow({
    	offset: new AMap.Pixel(16, -36)
    });
  	function markerClick(e){
    	infoWindow.setContent(e.target.content);
    	infoWindow.open(myMap,e.target.getPosition());
	}
	myMap.on('click',function(){
		infoWindow.close();
	});


});