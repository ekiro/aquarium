dofile("credentials.lua")
local t = require("ds18b20s")
local TEMP_PIN = 3

local HEATER_PIN = 1
local LIGHT_PIN = 2
local PUMP_PIN = 5

gpio.mode(HEATER_PIN, gpio.OUTPUT)
gpio.mode(LIGHT_PIN, gpio.OUTPUT)
gpio.mode(PUMP_PIN, gpio.OUTPUT)

local states = {
    temp = 0.0,
    heater = false,
    pump = true,
    light = false
}

wifi.setmode(wifi.STATION)

wifi.sta.config{
    ssid=wifi_data.ssid,
    pwd=wifi_data.pwd,
    save=false,
    got_ip_cb=function ()
        print("Config done, IP is "..wifi.sta.getip())
        sntp.sync(nil,
          function(sec, usec, server, info)
            print('sync', sec, usec, server)
          end,
          function()
           print('failed!')
          end
        )
    end
}
wifi.sta.connect(function()
    print("ESP8266 mode is: " .. wifi.getmode())
    print("The module MAC address is: " .. wifi.ap.getmac())
end)

-- Measure temperature, and send it to the server
cron.schedule("* * * * *", function(e)
  print("Every minute ")
  send_measurement()
end)


function disable_heater()
    print('disable heater')
    gpio.write(HEATER_PIN, gpio.LOW)
    states.heater = false
end

function enable_heater()
    print('enable heater')
    gpio.write(HEATER_PIN, gpio.HIGH)
    states.heater = true
end


function disable_light()
    print('disable light')
    gpio.write(LIGHT_PIN, gpio.LOW)
    states.light = false
end

function enable_light()
    print('enable light')
    gpio.write(LIGHT_PIN, gpio.HIGH)
    states.light = true
end

function update_states(config)
    if states.heater and states.temp >= config.temp then
        disable_heater()
    elseif not states.heater and states.temp <= (config.temp - config.temp_tolerance) then
        enable_heater()
    end
end

tmr.create():alarm(5000, tmr.ALARM_AUTO, function()
  print("temp:", t.readNumber(TEMP_PIN))
end)

function send_measurement()
  states.temp = t.readNumber(TEMP_PIN)
  ok, json = pcall(sjson.encode, {
    temp=states.temp,
    pump=states.pump,
    heater=states.heater,
    light=states.light,
    time=get_time(),
    uptime=tmr.now()/1000000,
  })
  if ok then
    print(json)
  else
    print("failed to encode!")
    return
  end
  http.post("http://aquarium.kiro.dev/measurement/" .. node.chipid() ,
    'Content-Type: application/json\r\nAuthorization: ' .. device_data.auth .. '\r\n',
    json,
    function(code, data)
      if (code ~= 200) then
        print("HTTP request failed" .. code)
        if (code > 0) then
            print(data)
        end
      else
       config = sjson.decode(data)
       update_states(config)
      end
  end)
end


function get_time()
    local tm = rtctime.epoch2cal(rtctime.get())
    return string.format("%04d-%02d-%02dT%02d:%02d:%02d", tm["year"], tm["mon"], tm["day"], tm["hour"], tm["min"], tm["sec"])
end