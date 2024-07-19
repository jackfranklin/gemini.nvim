local util = require("gemini.util")

local M = {}

M.setup = function()
  vim.api.nvim_create_user_command("GeminiChat", M.start_chat, {
    force = true,
    desc = "Google Gemini",
  })
end

M.start_chat = function()
  if M._split ~= nil then
    M._split:unmount()
    M._split = nil
  end

  M._split = util.make_split()
  M._split:mount()

  vim.ui.input({
    prompt = "[gemini.nvim] prompt: ",
    default = "",
  }, function(input_text)
    local context = {
      win_id = M._split.winid,
      bufnr = M._split.bufnr,
    }
    vim.api.nvim_call_function("_generative_ai_chat", { context, input_text })
  end)
end

return M
