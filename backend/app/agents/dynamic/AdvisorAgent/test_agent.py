import unittest

# This is a hypothetical AgentDefinition class that would parse the JSON output
# and represent the agent's configuration.
class MockAgentDefinition:
    def __init__(self, name, description, system_prompt, tools):
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.tools = tools

class TestAdvisorAgent(unittest.TestCase):

    def test_agent_definition_structure(self):
        # In a real scenario, this would load the agent definition JSON
        # and create an AgentDefinition instance from it.
        # For this test, we simulate the expected values.
        expected_name = "AdvisorAgent"
        expected_description = "A general-purpose agent providing comprehensive, well-researched, and actionable advice across various domains."
        expected_tools = ["web_search", "read_file", "write_file"]

        # Simulate an agent instance created from the generated configuration
        mock_agent_instance = MockAgentDefinition(
            name=expected_name,
            description=expected_description,
            system_prompt="Your system prompt content would go here...", # Actual content is checked for type/length
            tools=expected_tools
        )

        self.assertEqual(mock_agent_instance.name, expected_name, "Agent name does not match expected value.")
        self.assertEqual(mock_agent_instance.description, expected_description, "Agent description does not match expected value.")
        
        self.assertIsInstance(mock_agent_instance.system_prompt, str, "System prompt should be a string.")
        self.assertGreater(len(mock_agent_instance.system_prompt), 100, "System prompt is too short, indicating insufficient detail.")
        
        self.assertIsInstance(mock_agent_instance.tools, list, "Tools should be a list.")
        self.assertListEqual(sorted(mock_agent_instance.tools), sorted(expected_tools), "Agent tools do not match expected list.")
        self.assertTrue(all(isinstance(tool, str) for tool in mock_agent_instance.tools), "All tools in the list should be strings.")

if __name__ == '__main__':
    unittest.main()