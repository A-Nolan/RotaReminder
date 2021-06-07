from errbot import BotPlugin, botcmd

class Hello(BotPlugin):
    """Hello world test """

    @botcmd
    def hello(self, msg, args):
        return "Hello, world!"

    @botcmd
    def postToChannel(self, msg, args):
        self.send_card(
            to=self.build_identifier("#lab-day"),
            title="Card Test",
            summary="This is a card test to see how it works",
            body="Just saying hello to everyone in the channel",
            color="red",
        )

    def schedule(self):
        self.send_card(
            to=self.build_identifier("@aaron.nolan"),
            title="Schedule Test",
            summary="This is a card test to see how the schedule works",
            body="Just saying hello to everyone in the channel every 10 secs",
            color="red",
        )

    @botcmd
    def startSchedule(self, msg, args):
        self.start_poller(10, self.schedule)