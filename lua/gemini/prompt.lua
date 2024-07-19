local util = require("gemini.util")
local config = require("gemini.config")

local M = {}

M.setup = function()
  local register_prompt = function(_, command_name, menu, system_prompt)
    local gemini = function()
      M.show_stream_response(system_prompt)
    end

    vim.api.nvim_create_user_command(command_name, gemini, {
      force = true,
      desc = "Google Gemini",
    })

    vim.api.nvim_command("nnoremenu Gemini." .. menu:gsub(" ", "\\ ") .. " :" .. command_name .. "<CR>")
  end

  for _, item in pairs(config.get_menu_prompts()) do
    register_prompt(item.name, item.command_name, item.menu, item.prompt)
  end
end

M.prepare_code_prompt = function(prompt, bufnr)
  local wrap_code = function(code)
    local filetype = vim.api.nvim_get_option_value("filetype", { buf = bufnr })
    local code_markdown = "```" .. filetype .. "\n" .. code .. "\n```"
    return prompt .. "\n\n" .. code_markdown
  end

  local lines = vim.api.nvim_buf_get_lines(bufnr, 0, -1, false)
  local code = vim.fn.join(lines, "\n")
  return wrap_code(code)
end

M.show_stream_response = function(system_prompt)
  if M._split ~= nil then
    M._split:unmount()
    M._split = nil
  end
  local current = vim.api.nvim_get_current_buf()
  M._split = util.make_split()
  M._split:mount()

  local prompt = M.prepare_code_prompt(system_prompt, current)
  vim.defer_fn(function()
    vim.api.nvim_call_function("_gemini_api_stream_async", { M._split.bufnr, M._split.winid, prompt })
  end, 0)
end

return M
