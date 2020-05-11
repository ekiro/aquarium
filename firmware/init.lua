dofile("credentials.lua")
local t = require("ds18b20s")
local TEMP_PIN = 3

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
  print("Every minute " .. t.readNumber(TEMP_PIN))
end)


function send_measurement()
  states.temp = t.readNumber(TEMP_PIN)
  ok, json = pcall(sjson.encode, {
    temp=states.temp,
    pump=states.pump,
    heater=states.heater,
    light=states.light,
    time=get_time(),
  })
  if ok then
    print(json)
  else
    print("failed to encode!")
  end
  http.post("https://aquarium.kiro.dev/measurement/" .. node.chipid() ,
    'Content-Type: application/json\r\nAuthorization: ' .. device_data.auth .. '\r\n',
    json,
    function(code, data)
      if (code ~= 200) then
        print("HTTP request failed" .. code .. data)
      else
       config = sjson.decode(data)
       print(config) 
      end
  end)
end


function get_time()
    local tm = rtctime.epoch2cal(rtctime.get())
    return string.format("%04d-%02d-%02dT%02d:%02d:%02d", tm["year"], tm["mon"], tm["day"], tm["hour"], tm["min"], tm["sec"])
end