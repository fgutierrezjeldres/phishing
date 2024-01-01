/*
Template Name: Color Admin - Responsive Admin Dashboard Template build with Twitter Bootstrap 4
Version: 4.7.0
Author: Sean Ngu
Website: http://www.seantheme.com/color-admin/admin/
*/

Chart.defaults.global.defaultFontColor = COLOR_DARK;
Chart.defaults.global.defaultFontFamily = FONT_FAMILY;
Chart.defaults.global.defaultFontStyle = FONT_WEIGHT;



var lineChartData = {
	labels: ['0', '200', '400', '600', '800', '1000'],
	datasets: [{
		label: 'Precision',
		borderColor: COLOR_BLUE,
		pointBackgroundColor: COLOR_BLUE,
		pointRadius: 2,
		borderWidth: 2,
		backgroundColor: COLOR_BLUE_TRANSPARENT_3,
		data: [{% for data in df[["accuracy"]] %}
				"{{data}}"
				{% endfor %}]
	}, {
		label: 'Error',
		borderColor: COLOR_DARK_LIGHTER,
		pointBackgroundColor: COLOR_DARK,
		pointRadius: 2,
		borderWidth: 2,
		backgroundColor: COLOR_DARK_TRANSPARENT_3,
		data: [{% for data in df[["loss"]] %}
				"{{data}}"
				{% endfor %}]
	}]
};









var handleChartJs = function() {
	var ctx = document.getElementById('line-chart').getContext('2d');
	var lineChart = new Chart(ctx, {
		type: 'line',
		data: lineChartData
	});
};

var ChartJs = function () {
	"use strict";
	return {
		//main function
		init: function () {
			handleChartJs();
		}
	};
}();

$(document).ready(function() {
	ChartJs.init();
});