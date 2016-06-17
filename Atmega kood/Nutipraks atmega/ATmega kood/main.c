/*
 * ATmega kood.c
 *
 * Created: 27.05.2016 13:24.55
 * Author : Andres
 */ 

#define F_CPU 8000000

#include <avr/io.h>
#include <avr/power.h>
#include <avr/interrupt.h>
#include <util/delay.h>
#include <stdarg.h>
#include <string.h>
#include <stdlib.h>

#define RECEIVEBUFFERCOUNT (5)
#define RECEIVEBUFFERSIZE (64)
#define RECEIVEBUFFERCOUNTCOMMAND (5)
#define RECEIVEBUFFERSIZECOMMAND (64)

char receivedStrings [RECEIVEBUFFERCOUNT][RECEIVEBUFFERSIZE];
char receivedCommandsFromTheInternet[RECEIVEBUFFERCOUNTCOMMAND][RECEIVEBUFFERSIZECOMMAND];
volatile uint8_t beginning = 0;
volatile uint8_t end = 0;
volatile uint8_t beginningCommands = 0;
volatile uint8_t endCommands = 0;
volatile uint8_t sizeCommands = 0;
uint8_t commandCharsLeftToRead = 0;
uint8_t currentlyReceivingStringOffset = 0;
volatile uint8_t size = 0;
char tempCommandBuffer[RECEIVEBUFFERSIZE];
uint8_t ID;
volatile uint8_t temp = 0;

void sendString(char* string);
uint8_t startsWith(char* string1, char* string2);

void ledOn(uint8_t led){
	if(led < 6){
		PORTC |= 1<<led;
	}
	else if(led < 9){
		PORTB |= 1<<(led-6);
	}
	else if(led < 10){
		PORTD |= 1<<7;
	}
}

void ledOff(uint8_t led){
	if(led < 6){
		PORTC &= ~(1<<led);
	}
	else if(led < 9){
		PORTB &= ~(1<<(led-6));
	}
	else if(led < 10){
		PORTD &= ~(1<<7);
	}
}

void handleError(){
	//turn on the last led
	ledOn(9);
}

uint8_t wasError(){
	//return if the last led is on
	return PORTD&(1<<7);
}

void clearError(){
	PORTD &= ~(1<<7);
}

void restartOnError(){
	//restart the microcontroller in 4 seconds if there was an error
	if(wasError()){
		WDTCSR |= (1<<WDCE) | (1<<WDE);
		WDTCSR = (1<<WDE) | (1<<WDP3);
	}
}

ISR(USART_RX_vect){
	//PINC |= 1<<1;
	//receive data to a circular buffer, beginning points to the first string, end to the next string after the last one, size is how many slots are used
	//each segment, that ends with a newline, is put into the next slot, if the data is sent from another computer (it starts with "+IPD,"), it
	//is put into the receivedCommandsFromTheInternet buffer, from the lines the new line symbol is removed, for the commands from the internet
	//they are put there as is
	char c = UDR0;
	if(commandCharsLeftToRead){
		if(currentlyReceivingStringOffset < RECEIVEBUFFERSIZECOMMAND-1){
			receivedCommandsFromTheInternet[endCommands][currentlyReceivingStringOffset] = c;
			++currentlyReceivingStringOffset;
		}
		--commandCharsLeftToRead;
		if(commandCharsLeftToRead == 0){
			receivedCommandsFromTheInternet[endCommands][currentlyReceivingStringOffset] = 0;
			sizeCommands += 1;
			endCommands = (endCommands == (RECEIVEBUFFERCOUNTCOMMAND - 1)) ? 0 : (endCommands + 1);
			currentlyReceivingStringOffset = 0;
		}
	}
	else{
		receivedStrings[end][currentlyReceivingStringOffset] = c;
		if(currentlyReceivingStringOffset == 0 && size == RECEIVEBUFFERCOUNT){
			size -= 1;
			beginning = (beginning == (RECEIVEBUFFERCOUNT - 1)) ? 0 : (beginning + 1);
		}
		if(currentlyReceivingStringOffset == 0 && c == '>'){
			currentlyReceivingStringOffset++;
			c = '\n'; //end of command
		}
		if(c == ':' && startsWith(receivedStrings[end], "+IPD,")){
			commandCharsLeftToRead = atoi(&(receivedStrings[end][5]));
			temp = commandCharsLeftToRead;
			char tempBuffer[10];
			itoa(commandCharsLeftToRead, tempBuffer, 10);
			currentlyReceivingStringOffset = 0;
		}
		else if((c == '\n' && currentlyReceivingStringOffset != 0) || currentlyReceivingStringOffset >= RECEIVEBUFFERSIZE-1){
			receivedStrings[end][currentlyReceivingStringOffset] = 0;
			currentlyReceivingStringOffset = 0;
			size += 1;
			if(strcmp(receivedStrings[end], "ERROR") == 0 || strcmp(receivedStrings[end], "FAIL") == 0){
				handleError();
			}
			end = (end == (RECEIVEBUFFERCOUNT - 1)) ? 0 : (end + 1);
		}
		else if(c != '\r' && c != '\n'){
			++currentlyReceivingStringOffset;
		}
	}
}

uint8_t getLine(char* destination){
	//this waits for a line (not including data sent by another device), and copies it into the destination
	//copying is necessary, because we might receive new commands and they might overwrite the location of the line in the circular buffer,
	//updates the circular buffer beginning, because one command has been processed
	while(size == 0);
	cli();
	for(uint8_t n = 0; n < RECEIVEBUFFERSIZE; ++n){
		char c = receivedStrings[beginning][n];
		if(c == '\n'){
			destination[n] = 0;
			break;
		}
		destination[n] = receivedStrings[beginning][n];
	}
	size -= 1;
	beginning = (beginning == (RECEIVEBUFFERCOUNT - 1)) ? 0 : (beginning + 1);
	sei();
	return 1;
}

uint8_t startsWith(char* string1, char* string2){
	//1 if string1 starts with string2, 0 otherwise
	while(1){
		if(*string2 == 0){
			return 1;
		}
		else if (*string1 != *string2){
			return 0;
		}
		string1++;
		string2++;
	}
}

void sendString(char* string){
	//sends the given string as is to the wireless module
	while(1){
		if(*string == 0){
			break;
		}
		while(!(UCSR0A & (1<<UDRE0))){}
		UDR0 = *string;
		++string;
	}
}

void waitForACommand(char* destination){
	//this waits for a command received from another device and copies it to the destination, updates the circular buffer beginning, because one command has been processed
	while(sizeCommands == 0);
	cli();
	for(uint8_t i = 0; i < RECEIVEBUFFERSIZECOMMAND; ++i){
		destination[i] = receivedCommandsFromTheInternet[beginningCommands][i];
		if(destination[i] == 0){
			break;
		}
	}
	sizeCommands -= 1;
	beginningCommands = (beginningCommands == (RECEIVEBUFFERCOUNTCOMMAND - 1)) ? 0 : (beginningCommands + 1);
	sei();
}

uint8_t waitForOneOfTheLines(uint8_t count, ...){
	//can be given any number of arguments, returns if one of them is received and the return value is which command (starting with 0) was received
	//count is how many commands it 
	char tempBuffer[RECEIVEBUFFERSIZE];
	va_list args;
	while(1){
		va_start(args, count);
		getLine(tempBuffer);
		//PINB |= 1<<0;
		for(uint8_t i = 0; i < count; ++i){
			char* string = va_arg(args, char*);
			if(strcmp(string, tempBuffer) == 0){
				va_end(args);
				return i;
			}
		}
		va_end(args);
	}
}

void waitForOKorError(){
	waitForOneOfTheLines(3, "OK", "ERROR", "SEND OK");
}

void sendCommand(char* data){
	//this sends a command to the other device to which the wifi module is currently connected to
	//it handles all the communication with the wifi module to send the data
	uint8_t length = 0;
	while(data[length] != 0){
		++length;
	}
	sendString("AT+CIPSEND=");
	char buffer[16];
	itoa(length,buffer,10);
	sendString(buffer);
	sendString("\r\n");
	waitForOneOfTheLines(1, ">");
	sendString(data);
	waitForOKorError();
}

void setLeds(char* ledString){
	//sets the leds to the values, given in the string, beginning with the first led, for example "0101"
	for(uint8_t n = 0; n < strlen(ledString); ++n){
		if(ledString[n] == '0'){
			ledOff(n);
		}
		else if(ledString[n] == '1'){
			ledOn(n);
		}
	}
}

ISR(TIMER1_COMPA_vect){
	//flash a led to indicate power on
	PINB |= 1<<2;
}

int main(void)
{
	//clear the watchdog timer
	MCUSR &= ~(1<<WDRF);
	WDTCSR |= (1<<WDCE) | (1<<WDE);
	WDTCSR = 0;
	
	//timer for the power on led flash
	OCR1A = F_CPU/(1024*2);
	TCCR1B = (1<<WGM12)|(0b101<<CS10);
	TIMSK1 = 1<<OCIE1A;
	
	//enable the leds
	clock_prescale_set(clock_div_1);
	DDRC = 0x3f;
	DDRB = 7;
	DDRD = 1<<7;
	
	//enable the UART
	UCSR0B = (1<<RXEN0)|(1<<TXEN0)|(1<<RXCIE0);
	UCSR0C = (0b11<<UCSZ00);
	UBRR0 = 12;
	sei();
	
	//initialize the wifi module, at each step turn on the next led to indicate progress, if there was an error, wait for 4 seconds and restart
	sendString("AT\r\n");
	waitForOKorError();
	ledOn(0);
	restartOnError();
	
	sendString("AT+CWMODE=1\r\n");
	waitForOKorError();
	ledOn(1);
	restartOnError();
	
	//this only connects to the wifi network if not connected already
	sendString("AT+CWJAP?\r\n");
	if(waitForOneOfTheLines(2, "No AP", "OK") == 0){
		waitForOKorError();
		sendString("AT+CWJAP=\"ut-public\",\"\"\r\n");
		waitForOKorError();
	}
	ledOn(2);
	restartOnError();
	
	//close the current connection to indicate reset of the microcontroller
	sendString("AT+CIPCLOSE\r\n");
	waitForOKorError();
	ledOn(3);
	clearError();
	
	//connect to the Raspberry server
	sendString("AT+CIPSTART=\"TCP\",\"172.19.28.50\",8890\r\n");
	waitForOKorError();
	ledOn(4);
	restartOnError();
	
	setLeds("00000000");
	
	//this sends the data that the server wants, also receives an ID
	waitForACommand(tempCommandBuffer);
	sendCommand("name=Atmega;leds=00000000\n");
	waitForACommand(tempCommandBuffer);
	ID=atoi(tempCommandBuffer+strlen("ID="));
	sendCommand("OK\n");
	
	while(1){
		//wait for commands and react
		waitForACommand(tempCommandBuffer);
		if(startsWith(tempCommandBuffer, "param;leds=")){
			setLeds(tempCommandBuffer + strlen("param;leds="));
		}
		else if(startsWith(tempCommandBuffer, "FromServer=")){
			char* message = tempCommandBuffer + strlen("FromServer=");
			if(strcmp(message, "OFF\n") == 0){
				setLeds("00000000");
				sendCommand("OK\n");
				sendCommand("param;leds=00000000\n");
				waitForACommand(tempCommandBuffer);
			}
			else{
				sendCommand("Unknown Command\n");
			}
		}
	}
}

