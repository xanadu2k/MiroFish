{
  "env": {
    "VOLCENGINE_API_KEY": "5b049b7a-ac1c-4429-a6df-b1ad88120238"
  },
  "auth": {
    "profiles": {
      "volcengine:default": {
        "provider": "volcengine",
        "mode": "api_key"
      }
    }
  },
  "models": {
    "providers": {
      "volcengine": {
        "baseUrl": "https://ark.cn-beijing.volces.com/api/v3",
        "api": "openai-completions",
        "authHeader": true,
        "models": [{ "id": "glm-4-7-251222" }]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": { "primary": "volcengine/glm-4-7-251222" }
    }
  }
}

并且在 agent 鉴权文件加上：


{
  "version": 1,
  "profiles": {
    "volcengine:default": {
      "type": "api_key",
      "provider": "volcengine",
      "key": "5b049b7a-ac1c-4429-a6df-b1ad88120238"
    }
  }
}


 “帮我开个终端 tail -f 一下本项目的实时日志，别动进程，我就看看队列。”
 tail -f /Volumes/MasterDisk/Documents/Github/MiroFish/backend/logs/2026-04-20.log
