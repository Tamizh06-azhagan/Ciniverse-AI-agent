import app
print("\n--- AI TOOL ROUTER TESTS ---")

print("\n1. Movie list:")
print(app.route_ai_tool("What movies are available?"))

print("\n2. Leo showtimes:")
print(app.route_ai_tool("What are the showtimes for Leo?"))

print("\n3. Leo ticket price:")
print(app.route_ai_tool("What is the ticket price for Leo?"))

print("4. Total for 2 Leo tickets:")
print(app.route_ai_tool("How much for 2 Leo tickets?"))

print("\n--- AGENT WORKFLOW TEST ---")

print(
    app.run_agent_workflow(
        "How much for 2 Leo tickets?"
    )
)

print("\n--- AGENT RESPONSE TEST ---")

agent_result = app.run_agent_workflow(
    "How much for 2 Leo tickets?"
)

friendly_response = app.format_agent_response(agent_result)

print(friendly_response)
