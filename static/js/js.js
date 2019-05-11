const webPort = 5001;
var remoteServerFQDN1 = "";
var returnArray = [];
var config = "";
var streamAdminTableHTML = "";
var remoteServers = 0;

var Dashboard = function () {
    var global = {
        tooltipOptions: {
            placement: "right"
        },
        menuClass: ".c-menu"
    };

    var menuChangeActive = function menuChangeActive(el) {
        $(global.menuClass + " .is-active").removeClass("is-active");
        $(el).addClass("is-active");
    };

    var sidebarChangeWidth = function sidebarChangeWidth() {
        $("body").toggleClass("sidebar-is-reduced sidebar-is-expanded");
        $(".hamburger-toggle").toggleClass("is-opened");

        if ($("body").hasClass("sidebar-is-expanded")) {
            $('[data-toggle="tooltip"]').tooltip("destroy");
        } else {
            $('[data-toggle="tooltip"]').tooltip(global.tooltipOptions);
        }
    };

    var readTextFile = function (file, callback) {
        var rawFile = new XMLHttpRequest();
        rawFile.overrideMimeType("application/json");
        rawFile.open("GET", file, true);
        rawFile.setRequestHeader('Cache-Control', 'no-cache');
        rawFile.onreadystatechange = function () {
            if (rawFile.readyState === 4 && rawFile.status == "200") {
                callback(rawFile.responseText);
            }
        }
        rawFile.send(null);
    }

    return {
        init: function init() {
            $(document).click(function () {
                $.each($("input"), function () {
                    if ($(this).attr("type") != "search" && !$(this).hasClass("ignore-validation")) {
                        if ($(this).is(":visible")) {
                            $(this).prop('required', true);
                        } else {
                            $(this).prop('required', false);
                        }
                    }
                });
            });

            $(".js-hamburger").on("click", sidebarChangeWidth);

            $(".js-menu li").on("click", function (e) {
                menuChangeActive(e.currentTarget);
            });

            $('[data-toggle="tooltip"]').tooltip(global.tooltipOptions);

            var updateStreamAdministrators = function () {
                streamAdminTableHTML = '<table id="streamAdministratorsTable" class="table table-striped'
                streamAdminTableHTML += ' table-bordered table-hover table-responsive">';
                streamAdminTableHTML += '<thead><tr><th scope="col">#</th><th scope="col">Stream ID</th><th scope="col">';
                streamAdminTableHTML += 'Email Address</th></tr></thead><tbody>';

                readTextFile("ApprovalStreamsToEmailAddressMap.csv", function (text) {
                    $.each(text.split("\n"), function (key, value) {
                        if (value.split(",")[0].toLowerCase() != "streamid" && value.split(",")[0].length >= 1) {
                            streamAdminTableHTML += '<tr><th scope="row">' + key + '</th>';
                            streamAdminTableHTML += '<td>' + value.split(",")[0].trim() + '</td>'
                            streamAdminTableHTML += '<td>' + value.split(",")[1].trim() + '</td></tr>'
                        }
                    });

                    streamAdminTableHTML += '</tbody></table>';

                    $("#streamAdministratorsTableDiv").html(streamAdminTableHTML);
                    $('#streamAdministratorsTable').DataTable();
                });

            }

            var updatePageValues = function () {
                $('#remoteServers').empty();
                readTextFile("config.json", function (text) {
                    config = JSON.parse(text);

                    var flaskPort = config['port'];
                    if (flaskPort.trim().length >= 1) {
                        $("#flaskPort").val(flaskPort)
                    };
                    var onSameBox = config['installed_on_sense_server'];
                    if (onSameBox == "true") {
                        $("#onSameBox").prop('checked', true).change();
                    };

                    if ($('#onSameBox').prop('checked')) {
                        $('#nonLocalhostInstallDiv').css('display', 'none');
                    } else {
                        $('#nonLocalhostInstallDiv').css('display', 'inline');
                    }
                    var localServer = config['promote_on_custom_property_change']['local_server'];
                    if (localServer.trim().length >= 1) {
                        $("#localServer").val(localServer)
                    };
                    var localServerFQDN = config['promote_on_custom_property_change']['local_server_FQDN'];
                    if (localServerFQDN.trim().length >= 1) {
                        $("#localServerFQDN").val(localServerFQDN)
                    };

                    var remoteServerDropdownHTML = '<select id="remoteServerQRSSelect" class="form-control">';
                    $.each(config["promote_on_custom_property_change"]["remote_servers"], function (key, value) {
                        var remoteChunk = '<div id="remoteServer' + remoteServers + '">' +
                            '<div class="remote-minus-button"><i id="remoteServerSubtractButton' + remoteServers + '" class="fa fa-minus-circle fa-2x minus-button"></i></div>' +
                            '<div class="form-group">' +
                            '<label class="col-md-4 control-label" for="remoteServerFQDN' + remoteServers + '">Remote Server FQDN</label>' +
                            '<div class="col-md-6">' +
                            '<input id="remoteServerFQDN' + remoteServers + '" name="remoteServerFQDN' + remoteServers + '" type="text" placeholder="remote-server.domain.com" class="form-control input-md remote-server">' +
                            '</div>' +
                            '</div>' +
                            '<div class="form-group">' +
                            '<label class="col-md-4 control-label" for="remoteServerAlias' + remoteServers + '">Custom Property Alias</label>' +
                            '<div class="col-md-6">' +
                            '<input id="remoteServerAlias' + remoteServers + '" name="remoteServerAlias' + remoteServers + '" type="text" placeholder="alias" class="form-control input-md remote-server-alias">' +
                            '</div>' +
                            '</div>' +
                            '</div>';

                        $('#remoteServers').append(remoteChunk);

                        if (value["remote_server"].trim().length >= 1) {
                            $('#remoteServerFQDN' + remoteServers).val(value["remote_server"])
                            $('#remoteServerAlias' + remoteServers).val(value["server_alias"])
                            remoteServerDropdownHTML += '<option value="' + value["remote_server"] + '">' + value["server_alias"] + '</option>'
                        };

                        remoteServers += 1
                    });

                    remoteServerDropdownHTML += '</select>'
                    $('#remoteServerDropdown').html(remoteServerDropdownHTML);

                    if ($('.remote-server').length > 1) {
                        $('.minus-button').css('display', 'inline');
                    } else {
                        $('.minus-button').css('display', 'none');
                    }

                    var backendUserDirectory = config['promote_on_custom_property_change']['user_directory'];
                    if (backendUserDirectory.trim().length >= 1) {
                        $("#backendUserDirectory").val(backendUserDirectory)
                    };
                    var backendUserId = config['promote_on_custom_property_change']['user_id'];
                    if (backendUserId.trim().length >= 1) {
                        $("#backendUserId").val(backendUserId)
                    };
                    var targetServer = config['promote_on_custom_property_change']['custom_property_name_promote'];
                    if (targetServer.trim().length >= 1) {
                        $("#targetServer").val(targetServer)
                    };
                    var targetStreams = config['promote_on_custom_property_change']['custom_property_name_promote_stream'];
                    if (targetStreams.trim().length >= 1) {
                        $("#targetStreams").val(targetStreams)
                    };
                    var promotionApproval = config['promote_on_custom_property_change']['custom_property_name_promote_approval'];
                    if (promotionApproval.trim().length >= 1) {
                        $("#promotionApproval").val(promotionApproval)
                    };

                    var autoPromoteOnReload = config['promote_on_reload']['enabled'];
                    if (autoPromoteOnReload == "true") {
                        $("#autoPromoteOnReload").prop('checked', true).change();
                    };
                    var autoPromoteOnReloadProp = config['promote_on_reload']['custom_property_name'];
                    if (autoPromoteOnReloadProp.trim().length >= 1) {
                        $("#autoPromoteOnReloadProp").val(autoPromoteOnReloadProp)
                    };
                    var autoPromoteOnReloadTag = config['promote_on_reload']['tag_name'];
                    if (autoPromoteOnReloadTag.trim().length >= 1) {
                        $("#autoPromoteOnReloadTag").val(autoPromoteOnReloadTag)
                    };

                    if ($('#autoPromoteOnReload').prop('checked')) {
                        $('#autoPromoteOnReloadDiv').css('display', 'inline');
                    } else {
                        $('#autoPromoteOnReloadDiv').css('display', 'none');
                    }

                    var autoUnpublish = config['promote_on_custom_property_change']['auto_unpublish_on_approve_or_deny']['auto_unpublish'];
                    if (autoUnpublish == "true") {
                        $("#autoUnpublish").prop('checked', true).change();
                    };
                    var promotionUnpublish = config['promote_on_custom_property_change']['auto_unpublish_on_approve_or_deny']['custom_property_name'];
                    if (promotionUnpublish.trim().length >= 1) {
                        $("#promotionUnpublish").val(promotionUnpublish)
                    };

                    if ($('#autoUnpublish').prop('checked')) {
                        $('#promotionUnpublishDiv').css('display', 'none');
                    } else {
                        $('#promotionUnpublishDiv').css('display', 'inline');
                    }

                    var emailEnabledButton = config['promote_on_custom_property_change']['email_config']['promotion_email_alerts'];
                    if (emailEnabledButton == "true") {
                        $("#emailEnabledButton").prop('checked', true).change();
                    };

                    if ($('#emailEnabledButton').prop('checked')) {
                        $('#emailDiv').css('display', 'inline');
                    } else {
                        $('#emailDiv').css('display', 'none');
                    }

                    var udcEmailExistsButton = config['promote_on_custom_property_change']['email_config']['email_UDC_attribute_exists'];
                    if (udcEmailExistsButton == "true") {
                        $("#udcEmailExistsButton").prop('checked', true).change();
                    };
                    var emailAlertOnPublishTo = config['promote_on_custom_property_change']['email_config']['custom_property_name_stream_alert_on_publish'];
                    if (emailAlertOnPublishTo.trim().length >= 1) {
                        $("#emailAlertOnPublishTo").val(emailAlertOnPublishTo)
                    };
                    var smtp = config['promote_on_custom_property_change']['email_config']['promotion_SMTP'];
                    if (smtp.trim().length >= 1) {
                        $("#smtp").val(smtp)
                    };
                    var smtpPort = config['promote_on_custom_property_change']['email_config']['promotion_SMTP_port'];
                    if (smtpPort.trim().length >= 1) {
                        $("#smtpPort").val(smtpPort)
                    };
                    var emailAddress = config['promote_on_custom_property_change']['email_config']['promotion_sender_email'];
                    if (emailAddress.trim().length >= 1) {
                        $("#emailAddress").val(emailAddress)
                    };
                    var emailPassword = config['promote_on_custom_property_change']['email_config']['promotion_sender_pass'];
                    if (emailPassword.trim().length >= 1) {
                        $("#emailPassword").val(emailPassword)
                    };

                    var s3versioningEnabledButton = config['promote_on_custom_property_change']['app_version_on_change']['enabled'];
                    if (s3versioningEnabledButton == "true") {
                        $("#s3versioningEnabledButton").prop('checked', true).change();
                    };

                    if ($('#s3versioningEnabledButton').prop('checked')) {
                        $('#versioningDiv').css('display', 'inline');
                    } else {
                        $('#versioningDiv').css('display', 'none');
                    }

                    var s3autoVersioningEnabledButton = config['promote_on_custom_property_change']['app_version_on_change']['auto_version_on_promote'];
                    if (s3autoVersioningEnabledButton == "true") {
                        $("#s3autoVersioningEnabledButton").prop('checked', true).change();
                    };

                    if ($('#s3autoVersioningEnabledButton').prop('checked')) {
                        $('#s3VersioningPropertyDiv').css('display', 'none');
                    } else {
                        $('#s3VersioningPropertyDiv').css('display', 'inline');
                    }

                    var s3VersioningProperty = config['promote_on_custom_property_change']['app_version_on_change']['custom_property_name'];
                    if (s3VersioningProperty.trim().length >= 1) {
                        $("#s3VersioningProperty").val(s3VersioningProperty)
                    };
                    var s3bucket = config['promote_on_custom_property_change']['app_version_on_change']['s3_bucket'];
                    if (s3bucket.trim().length >= 1) {
                        $("#s3bucket").val(s3bucket)
                    };
                    var s3bucketPrefix = config['promote_on_custom_property_change']['app_version_on_change']['prefix'];
                    if (s3bucketPrefix.trim().length >= 1) {
                        $("#s3bucketPrefix").val(s3bucketPrefix)
                    };

                    var logLevel = config['logging']['log_level'];
                    if (logLevel.trim().length >= 1) {
                        $("#logLevel").val(logLevel)
                    };
                    var notificationLogSize = config['logging']['notification_log_bytes'];
                    if (notificationLogSize.trim().length >= 1) {
                        $("#notificationLogSize").val(notificationLogSize / 1000000)
                    };
                    var notificationRollingLogs = config['logging']['notification_log_rolling_backup_num'];
                    if (notificationRollingLogs.trim().length >= 1) {
                        $("#notificationRollingLogs").val(notificationRollingLogs)
                    };
                    var otherLogSize = config['logging']['other_logs_bytes'];
                    if (otherLogSize.trim().length >= 1) {
                        $("#otherLogSize").val(otherLogSize / 1000000)
                    };
                    var otherRollingLogs = config['logging']['other_logs_rolling_backup_num'];
                    if (otherRollingLogs.trim().length >= 1) {
                        $("#otherRollingLogs").val(otherRollingLogs)
                    };
                });
            }

            updatePageValues();
            updateStreamAdministrators();

            $('a[data-toggle="tab"]').on('shown.bs.tab', function (e) {
                var activeTab = $(e.target).attr("href")
                if (activeTab == '#qrs-test') {
                    $('#submitButtonDiv').hide();
                } else {
                    $('#submitButtonDiv').show();
                }
            });

            $("#smtpTestButton").prop("disabled", true);

            $('#onSameBox').change(function () {
                if ($('#nonLocalhostInstallDiv').css('display') == 'none')
                    $('#nonLocalhostInstallDiv').css('display', 'inline');
                else
                    $('#nonLocalhostInstallDiv').css('display', 'none');
            });

            $(document).on("click", function () {
                if ($('.remote-server').length > 1) {
                    $('.minus-button').css('display', 'inline');
                } else {
                    $('.minus-button').css('display', 'none');
                }
            })

            $('#autoPromoteOnReload').change(function () {
                if ($('#autoPromoteOnReloadDiv').css('display') == 'none')
                    $('#autoPromoteOnReloadDiv').css('display', 'inline');
                else
                    $('#autoPromoteOnReloadDiv').css('display', 'none');
            });

            $('#autoUnpublish').change(function () {
                if ($('#promotionUnpublishDiv').css('display') == 'none')
                    $('#promotionUnpublishDiv').css('display', 'inline');
                else
                    $('#promotionUnpublishDiv').css('display', 'none');
            });

            $('#emailEnabledButton').change(function () {
                if ($('#emailDiv').css('display') == 'none')
                    $('#emailDiv').css('display', 'inline');
                else
                    $('#emailDiv').css('display', 'none');
            });

            $('#s3versioningEnabledButton').change(function () {
                if ($('#versioningDiv').css('display') == 'none')
                    $('#versioningDiv').css('display', 'inline');
                else
                    $('#versioningDiv').css('display', 'none');
            });

            $('#s3autoVersioningEnabledButton').change(function () {
                if ($('#s3VersioningPropertyDiv').css('display') == 'none')
                    $('#s3VersioningPropertyDiv').css('display', 'inline');
                else
                    $('#s3VersioningPropertyDiv').css('display', 'none');
            });

            $('#smtpTestDestination').on('input', function () {
                if ($('#smtpTestDestination').val().includes('@') && $('#smtpTestDestination').val().length > 1) {
                    if ($("#smtpTestButton").is(":disabled")) {
                        $("#smtpTestButton").prop("disabled", false);
                    }
                } else {
                    $("#smtpTestButton").prop("disabled", true);
                }
            });

            $('#remoteServerAddButton').on('click', function () {
                if ($('#remoteServerFQDN' + remoteServers).length) {
                    remoteServers += 1
                }
                $('#remoteServers').append(
                    '<div id="remoteServer' + remoteServers + '">' +
                    '<div class="remote-minus-button"><i id="remoteServerSubtractButton' + remoteServers + '" class="fa fa-minus-circle fa-2x minus-button"></i></div>' +
                    '<div class="form-group">' +
                    '<label class="col-md-4 control-label" for="remoteServerFQDN' + remoteServers + '">Remote Server FQDN</label>' +
                    '<div class="col-md-6">' +
                    '<input id="remoteServerFQDN' + remoteServers + '" name="remoteServerFQDN' + remoteServers + '" type="text" placeholder="remote-server.domain.com" class="form-control input-md remote-server">' +
                    '</div>' +
                    '</div>' +
                    '<div class="form-group">' +
                    '<label class="col-md-4 control-label" for="remoteServerAlias' + remoteServers + '">Custom Property Alias</label>' +
                    '<div class="col-md-6">' +
                    '<input id="remoteServerAlias' + remoteServers + '" name="remoteServerAlias' + remoteServers + '" type="text" placeholder="alias" class="form-control input-md remote-server-alias">' +
                    '</div>' +
                    '</div>' +
                    '</div>'
                );
                remoteServers += 1
            });

            // REMOVE REMOTE SERVER
            $(document).on("click", '.minus-button', function () {
                $('#remoteServer' + this.id.substring('remoteServerSubtractButton'.length)).remove();
                remoteServers -= 1;
            });

            var getAllFormValues = function () {
                returnArray = [];
                $("input").each(function () {
                    returnArray.push([this.id, this.value])
                });

                return returnArray
            }

            var buildConfigJSON = function (returnArray) {
                remoteServers = 0;
                config['promote_on_custom_property_change']['remote_servers'] = [];
                $.each(returnArray, function (key, array) {
                    if (array[0] == 'flaskPort') {
                        config['port'] = array[1];
                    } else if (array[0] == 'onSameBox') {
                        var id = "#" + array[0]
                        if ($(id).prop("checked") == true) {
                            config['installed_on_sense_server'] = "true";
                        } else {
                            config['installed_on_sense_server'] = "false";
                        }
                    } else if (array[0] == 'localServer') {
                        config['promote_on_custom_property_change']['local_server'] = array[1];
                    } else if (array[0] == 'localServerFQDN') {
                        config['promote_on_custom_property_change']['local_server_FQDN'] = array[1];
                    } else if (array[0].includes("remoteServerFQDN")) {
                        config['promote_on_custom_property_change']['remote_servers'].push({
                            "remote_server": array[1],
                            "server_alias": $('#remoteServerAlias' + array[0].substring('remoteServerFQDN'.length)).val()
                        })
                    } else if (array[0] == 'backendUserDirectory') {
                        config['promote_on_custom_property_change']['user_directory'] = array[1];
                    } else if (array[0] == 'backendUserId') {
                        config['promote_on_custom_property_change']['user_id'] = array[1];
                    } else if (array[0] == 'targetServer') {
                        config['promote_on_custom_property_change']['custom_property_name_promote'] = array[1];
                    } else if (array[0] == 'targetStreams') {
                        config['promote_on_custom_property_change']['custom_property_name_promote_stream'] = array[1];
                    } else if (array[0] == 'promotionApproval') {
                        config['promote_on_custom_property_change']['custom_property_name_promote_approval'] = array[1];
                    } else if (array[0] == 'autoPromoteOnReload') {
                        var id = "#" + array[0]
                        if ($(id).prop("checked") == true) {
                            config['promote_on_reload']['enabled'] = "true";
                        } else {
                            config['promote_on_reload']['enabled'] = "false";
                        }
                    } else if (array[0] == 'autoPromoteOnReloadProp') {
                        config['promote_on_reload']['custom_property_name'] = array[1];
                    } else if (array[0] == 'autoPromoteOnReloadTag') {
                        config['promote_on_reload']['tag_name'] = array[1];
                    } else if (array[0] == 'autoUnpublish') {
                        var id = "#" + array[0]
                        if ($(id).prop("checked") == true) {
                            config['promote_on_custom_property_change']['auto_unpublish_on_approve_or_deny']['auto_unpublish'] = "true";
                        } else {
                            config['promote_on_custom_property_change']['auto_unpublish_on_approve_or_deny']['auto_unpublish'] = "false";
                        }
                    } else if (array[0] == 'promotionUnpublish') {
                        config['promote_on_custom_property_change']['auto_unpublish_on_approve_or_deny']['custom_property_name'] = array[1];
                    } else if (array[0] == 'emailEnabledButton') {
                        var id = "#" + array[0]
                        if ($(id).prop("checked") == true) {
                            config['promote_on_custom_property_change']['email_config']['promotion_email_alerts'] = "true";
                        } else {
                            config['promote_on_custom_property_change']['email_config']['promotion_email_alerts'] = "false";
                        }
                    } else if (array[0] == 'udcEmailExistsButton') {
                        var id = "#" + array[0]
                        if ($(id).prop("checked") == true) {
                            config['promote_on_custom_property_change']['email_config']['email_UDC_attribute_exists'] = "true";
                        } else {
                            config['promote_on_custom_property_change']['email_config']['email_UDC_attribute_exists'] = "false";
                        }
                    } else if (array[0] == 'emailAlertOnPublishTo') {
                        config['promote_on_custom_property_change']['email_config']['custom_property_name_stream_alert_on_publish'] = array[1];
                    } else if (array[0] == 'smtp') {
                        config['promote_on_custom_property_change']['email_config']['promotion_SMTP'] = array[1];
                    } else if (array[0] == 'smtpPort') {
                        config['promote_on_custom_property_change']['email_config']['promotion_SMTP_port'] = array[1];
                    } else if (array[0] == 'emailAddress') {
                        config['promote_on_custom_property_change']['email_config']['promotion_sender_email'] = array[1];
                    } else if (array[0] == 'emailPassword') {
                        config['promote_on_custom_property_change']['email_config']['promotion_sender_pass'] = array[1];
                    } else if (array[0] == 's3versioningEnabledButton') {
                        var id = "#" + array[0]
                        if ($(id).prop("checked") == true) {
                            config['promote_on_custom_property_change']['app_version_on_change']['enabled'] = "true";
                        } else {
                            config['promote_on_custom_property_change']['app_version_on_change']['enabled'] = "false";
                        }
                    } else if (array[0] == 's3autoVersioningEnabledButton') {
                        var id = "#" + array[0]
                        if ($(id).prop("checked") == true) {
                            config['promote_on_custom_property_change']['app_version_on_change']['auto_version_on_promote'] = "true";
                        } else {
                            config['promote_on_custom_property_change']['app_version_on_change']['auto_version_on_promote'] = "false";
                        }
                    } else if (array[0] == 's3VersioningProperty') {
                        config['promote_on_custom_property_change']['app_version_on_change']['custom_property_name'] = array[1];
                    } else if (array[0] == 's3bucket') {
                        config['promote_on_custom_property_change']['app_version_on_change']['s3_bucket'] = array[1];
                    } else if (array[0] == 's3bucketPrefix') {
                        config['promote_on_custom_property_change']['app_version_on_change']['prefix'] = array[1];
                    } else if (array[0] == 'logLevel') {
                        config['logging']['log_level'] = array[1];
                    } else if (array[0] == 'notificationLogSize') {
                        config['logging']['notification_log_bytes'] = (array[1] * 1000000).toString();
                    } else if (array[0] == 'notificationRollingLogs') {
                        config['logging']['notification_log_rolling_backup_num'] = array[1];
                    } else if (array[0] == 'otherLogSize') {
                        config['logging']['other_logs_bytes'] = (array[1] * 1000000).toString();
                    } else if (array[0] == 'otherRollingLogs') {
                        config['logging']['other_logs_rolling_backup_num'] = array[1];
                    }
                });
            }

            $("#settings-form").submit(function (event) {
                getAllFormValues()
                buildConfigJSON(returnArray);

                if ($('#settings-form')[0].checkValidity() == true) {
                    $.ajax({
                        contentType: 'application/json',
                        data: JSON.stringify(config),
                        dataType: 'json',
                        success: function (data) {
                            updatePageValues();
                            updateStreamAdministrators();
                            showAlert("#writeSuccess", 3000);
                        },
                        error: function (textStatus, errorThrown) {
                            console.log("Error", textStatus, errorThrown);
                            showAlert("#writeFailure", 3000);
                        },
                        type: 'POST',
                        processData: false,
                        url: "http://localhost:" + webPort + "/write-config"
                    });
                }
                event.preventDefault();
            });

        }
    };
}();

Dashboard.init();

var showAlert = function (id, delay) {
    var alert = $(id);
    var timeOut;
    $(id).css('display', 'hidden');
    alert.appendTo('.page-alerts');
    alert.slideDown();

    delay = parseInt(delay);
    clearTimeout(timeOut);
    timeOut = window.setTimeout(function () {
        alert.slideUp();
    }, delay);
}

var qrsTest = function (server_input) {
    if (server_input == "remote") {
        serverType = "remote"
        server = $("#remoteServerQRSSelect option:selected").val();
        serverAlias = $("#remoteServerQRSSelect option:selected").text();
    } else {
        serverType = "local";
        serverAlias = undefined;
        if ($('#onSameBox').prop('checked')) {
            server = "localhost";
        } else {
            server = $("#localServer").val();
        }
    }
    var data = {
        "server": server,
        "serverAlias": serverAlias,
        "serverType": serverType
    }
    $.ajax({
        complete: function (data) {
            var responseText = data.responseText;
            if (data.responseText.substring(2, 7) !== "Error") {
                if (serverType == "local") {
                    $("#qrs-testLocalResponse").text(responseText);
                    $("#localResponseIcon").html('<i class="fa fa-check fa-2x qrs-response-icon"></i>');
                } else {
                    $("#qrs-testRemoteResponse").text(responseText);
                    $("#remoteResponseIcon").html('<i class="fa fa-check fa-2x qrs-response-icon"></i>');
                }
            } else {
                if (serverType == "local") {
                    $("#qrs-testLocalResponse").text(responseText);
                    $("#localResponseIcon").html('<i class="fa fa-exclamation-triangle fa-2x qrs-response-icon"></i>');
                } else {
                    $("#qrs-testRemoteResponse").text(responseText);
                    $("#remoteResponseIcon").html('<i class="fa fa-exclamation-triangle fa-2x qrs-response-icon"></i>');
                }
            }
        },
        data: JSON.stringify(data),
        contentType: "application/json",
        type: 'POST',
        processData: false,
        url: "http://localhost:" + webPort + "/qrs-test"
    });
}

var smtpTest = function () {
    showAlert("#workingOnIt", 3000);
    var data = {
        "smtp": $("#smtp").val(),
        "smtp_port": $("#smtpPort").val(),
        "sender_address": $("#emailAddress").val(),
        "password": $("#emailPassword").val(),
        "destination_address": $("#smtpTestDestination").val()
    }
    $.ajax({
        complete: function (data) {
            var responseText = data.responseText;
            if (data.responseText == "200") {
                showAlert("#smtpTestSuccess", 3000);
            } else {
                showAlert("#smtpTestError", 3000)
            }
        },
        data: JSON.stringify(data),
        contentType: "application/json",
        type: 'POST',
        processData: false,
        url: "http://localhost:" + webPort + "/smtp-test"
    });
}