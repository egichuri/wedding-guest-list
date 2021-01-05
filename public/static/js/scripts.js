/* eslint-disable */
function ErrorPage(container, pageType, templateName) {
  this.$container = $(container);
  this.$contentContainer = this.$container.find(templateName == 'sign' ? '.sign-container' : '.content-container');
  this.pageType = pageType;
  this.templateName = templateName;
}

ErrorPage.prototype.centerContent = function () {
  var containerHeight = this.$container.outerHeight()
    , contentContainerHeight = this.$contentContainer.outerHeight()
    , top = (containerHeight - contentContainerHeight) / 2
    , offset = this.templateName == 'sign' ? -100 : 0;

  this.$contentContainer.css('top', top + offset);
};

ErrorPage.prototype.initialize = function () {
  var self = this;

  this.centerContent();
  this.$container.on('resize', function (e) {
    e.preventDefault();
    e.stopPropagation();
    self.centerContent();
  });

  // fades in content on the plain template
  if (this.templateName == 'plain') {
    window.setTimeout(function () {
      self.$contentContainer.addClass('in');
    }, 500);
  }

  // swings sign in on the sign template
  if (this.templateName == 'sign') {
    $('.sign-container').animate({ textIndent: 0 }, {
      step: function (now) {
        $(this).css({
          transform: 'rotate(' + now + 'deg)',
          'transform-origin': 'top center'
        });
      },
      duration: 1000,
      easing: 'easeOutBounce'
    });
  }
};


ErrorPage.prototype.createTimeRangeTag = function (start, end) {
  return (
    '<time utime=' + start + ' simple_format="MMM DD, YYYY HH:mm">' + start + '</time> - <time utime=' + end + ' simple_format="MMM DD, YYYY HH:mm">' + end + '</time>.'
  )
};


ErrorPage.prototype.handleStatusFetchSuccess = function (pageType, data) {
  if (pageType == '503') {
    $('#replace-with-fetched-data').html(data.status.description);
  } else {
    if (!!data.scheduled_maintenances.length) {
      var maint = data.scheduled_maintenances[0];
      $('#replace-with-fetched-data').html(this.createTimeRangeTag(maint.scheduled_for, maint.scheduled_until));
      $.fn.localizeTime();
    }
    else {
      $('#replace-with-fetched-data').html('<em>(there are no active scheduled maintenances)</em>');
    }
  }
};


ErrorPage.prototype.handleStatusFetchFail = function (pageType) {
  $('#replace-with-fetched-data').html('<em>(enter a valid Statuspage url)</em>');
};


ErrorPage.prototype.fetchStatus = function (pageUrl, pageType) {
  if (!pageUrl || !pageType || pageType == '404') return;

  var url = ''
    , self = this;

  if (pageType == '503') {
    url = pageUrl + '/api/v2/status.json';
  }
  else {
    url = pageUrl + '/api/v2/scheduled-maintenances/active.json';
  }

  $.ajax({
    type: "GET",
    url: url,
  }).success(function (data, status) {
    self.handleStatusFetchSuccess(pageType, data);
  }).fail(function (xhr, msg) {
    self.handleStatusFetchFail(pageType);
  });

};
var ep = new ErrorPage('body', "404", "background");
ep.initialize();

// hack to make sure content stays centered >_<
$(window).on('resize', function () {
  $('body').trigger('resize')
});
/*!

 =========================================================
 * Light Bootstrap Dashboard - v1.4.0
 =========================================================

 * Product Page: http://www.creative-tim.com/product/light-bootstrap-dashboard
 * Copyright 2017 Creative Tim (http://www.creative-tim.com)
 * Licensed under MIT (https://github.com/creativetimofficial/light-bootstrap-dashboard/blob/master/LICENSE.md)

 =========================================================

 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

 */

var searchVisible = 0;
var transparent = true;

var transparentDemo = true;
var fixedTop = false;

var navbar_initialized = false;

$(document).ready(function () {
  window_width = $(window).width();

  // check if there is an image set for the sidebar's background
  lbd.checkSidebarImage();

  // Init navigation toggle for small screens
  lbd.initRightMenu();

  //  Activate the tooltips
  $('[rel="tooltip"]').tooltip();

  $('.form-control').on("focus", function () {
    $(this).parent('.input-group').addClass("input-group-focus");
  }).on("blur", function () {
    $(this).parent(".input-group").removeClass("input-group-focus");
  });

  // Fixes sub-nav not working as expected on IOS
  $('body').on('touchstart.dropdown', '.dropdown-menu', function (e) { e.stopPropagation(); });
});

$(document).on('click', '.navbar-toggle', function () {
  $toggle = $(this);

  if (lbd.misc.navbar_menu_visible == 1) {
    $('html').removeClass('nav-open');
    lbd.misc.navbar_menu_visible = 0;
    $('#bodyClick').remove();
    setTimeout(function () {
      $toggle.removeClass('toggled');
    }, 550);
  } else {
    setTimeout(function () {
      $toggle.addClass('toggled');
    }, 580);
    div = '<div id="bodyClick"></div>';
    $(div).appendTo('body').click(function () {
      $('html').removeClass('nav-open');
      lbd.misc.navbar_menu_visible = 0;
      setTimeout(function () {
        $toggle.removeClass('toggled');
        $('#bodyClick').remove();
      }, 550);
    });

    $('html').addClass('nav-open');
    lbd.misc.navbar_menu_visible = 1;
  }
});

$(window).on('resize', function () {
  if (navbar_initialized) {
    lbd.initRightMenu();
    navbar_initialized = true;
  }
});

lbd = {
  misc: {
    navbar_menu_visible: 0
  },

  checkSidebarImage: function () {
    $sidebar = $('.sidebar');
    image_src = $sidebar.data('image');

    if (image_src !== undefined) {
      sidebar_container = '<div class="sidebar-background" style="background-image: url(' + image_src + ') "/>'
      $sidebar.append(sidebar_container);
    }
  },

  initRightMenu: debounce(function () {
    if (!navbar_initialized) {
      $sidebar_wrapper = $('.sidebar-wrapper');
      $navbar = $('nav').find('.navbar-collapse').html();

      mobile_menu_content = '';

      nav_content = $navbar;

      nav_content = '<ul class="nav nav-mobile-menu">' + nav_content + '</ul>';

      // navbar_form = $('nav').find('.navbar-form').get(0).outerHTML;

      $sidebar_nav = $sidebar_wrapper.find(' > .nav');

      // insert the navbar form before the sidebar list
      $nav_content = $(nav_content);
      // $navbar_form = $(navbar_form);
      $nav_content.insertBefore($sidebar_nav);
      // $navbar_form.insertBefore($nav_content);

      $(".sidebar-wrapper .dropdown .dropdown-menu > li > a").click(function (event) {
        event.stopPropagation();

      });

      mobile_menu_initialized = true;
    } else {
      if ($(window).width() > 991) {
        // reset all the additions that we made for the sidebar wrapper only if the screen is bigger than 991px
        // $sidebar_wrapper.find('.navbar-form').remove();
        $sidebar_wrapper.find('.nav-mobile-menu').remove();

        mobile_menu_initialized = false;
      }
    }
  }, 200)
}


// Returns a function, that, as long as it continues to be invoked, will not
// be triggered. The function will be called after it stops being called for
// N milliseconds. If `immediate` is passed, trigger the function on the
// leading edge, instead of the trailing.

function debounce(func, wait, immediate) {
  var timeout;
  return function () {
    var context = this, args = arguments;
    clearTimeout(timeout);
    timeout = setTimeout(function () {
      timeout = null;
      if (!immediate) func.apply(context, args);
    }, wait);
    if (immediate && !timeout) func.apply(context, args);
  };
};
