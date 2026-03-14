import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { ChatInput } from "../ChatInput";

describe("ChatInput", () => {
  it("renders an input and send button", () => {
    render(<ChatInput onSend={jest.fn()} />);
    expect(screen.getByLabelText("Message input")).toBeInTheDocument();
    expect(screen.getByLabelText("Send message")).toBeInTheDocument();
  });

  it("calls onSend with trimmed text when button clicked", async () => {
    const onSend = jest.fn();
    render(<ChatInput onSend={onSend} />);

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "  Hello world  ");
    await userEvent.click(screen.getByLabelText("Send message"));

    expect(onSend).toHaveBeenCalledWith("Hello world");
  });

  it("calls onSend on Enter key press", async () => {
    const onSend = jest.fn();
    render(<ChatInput onSend={onSend} />);

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "test message{Enter}");

    expect(onSend).toHaveBeenCalledWith("test message");
  });

  it("does not call onSend on Shift+Enter", async () => {
    const onSend = jest.fn();
    render(<ChatInput onSend={onSend} />);

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "line one{Shift>}{Enter}{/Shift}line two");

    expect(onSend).not.toHaveBeenCalled();
  });

  it("disables input and button when isLoading is true", () => {
    render(<ChatInput onSend={jest.fn()} isLoading />);
    expect(screen.getByLabelText("Message input")).toBeDisabled();
    expect(screen.getByLabelText("Agent is responding")).toBeDisabled();
  });

  it("does not call onSend when input is empty", async () => {
    const onSend = jest.fn();
    render(<ChatInput onSend={onSend} />);

    await userEvent.click(screen.getByLabelText("Send message"));
    expect(onSend).not.toHaveBeenCalled();
  });

  it("clears input after sending", async () => {
    render(<ChatInput onSend={jest.fn()} />);

    const input = screen.getByLabelText("Message input");
    await userEvent.type(input, "hello{Enter}");

    expect(input).toHaveValue("");
  });
});
